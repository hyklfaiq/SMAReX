"""The upload pipeline.

This module is the heart of SMAReX and encodes the required order of
operations:

    1. pre-flight file validation (extension, MIME, size, PDF magic bytes)
    2. SHA-256 hash
    3. VirusTotal scan                       <-- nothing is stored before this
    4. reject: log the verdict, store nothing, return an error
    5. Supabase Storage upload (only now the file exists)
    6. resources row written as 'processing'
    7. pypdf text extraction
    8. Hugging Face summarisation
    9. summary + keywords saved
    10. resource marked 'published'

Step 8 is failure-isolated: if extraction or the model fails, the safely
stored file is kept, ``ai_summary_status`` records the failure, and the
resource is still published. AI problems never destroy a stored file.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import Summarizer, SummaryResult, SummaryStatus
from app.ai.preprocess import first_sentences
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    ConflictError,
    MaliciousFileError,
    SecurityScanError,
    StorageError,
    SuspiciousFileError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models import (
    AiSummaryStatus,
    PublicationStatus,
    Resource,
    ScanStatus,
    SecurityLog,
    SecurityStatus,
)
from app.pdf.extractor import extract_text
from app.schemas import ResourceCreate
from app.security.file_validation import validate_upload
from app.storage.supabase_storage import SupabaseStorage, build_object_path

from app.virus_total.client import ScanOutcome, VirusTotalClient

logger = get_logger(__name__)


class UploadPipeline:
    """Runs the upload flow. Collaborators are injected so tests can substitute
    a stub VirusTotal client or summariser without touching the network."""

    def __init__(
        self,
        scanner: VirusTotalClient,
        storage: SupabaseStorage,
        summarizer: Summarizer,
        settings: Settings | None = None,
    ) -> None:
        self.scanner = scanner
        self.storage = storage
        self.summarizer = summarizer
        self.settings = settings or get_settings()

    async def run(
        self,
        *,
        db: AsyncSession,
        owner_id: uuid.UUID,
        payload: ResourceCreate,
        file_bytes: bytes,
        raw_filename: str | None,
        content_type: str | None,
    ) -> UploadResult:
        # -- 1. pre-flight validation -------------------------------------
        validated = validate_upload(
            filename=raw_filename,
            content_type=content_type,
            size=len(file_bytes),
            head=file_bytes[:1024],
            settings=self.settings,
        )

        # -- 2. hash ------------------------------------------------------
        from app.security.hashing import sha256_bytes

        file_hash = sha256_bytes(file_bytes)

        # -- 3. VirusTotal ------------------------------------------------
        # A scanner outage must not silently publish the file, so this is
        # fail-closed: if we cannot get a verdict, nothing is stored.
        try:
            scan = await self.scanner.scan_bytes(file_bytes, validated.filename)
        except Exception as exc:
            await self._log_scan(
                db,
                owner_id=owner_id,
                filename=validated.filename,
                size=validated.size,
                file_hash=file_hash,
                status=ScanStatus.ERROR,
                details=f"Security scan could not be completed: {type(exc).__name__}",
            )
            await db.commit()
            logger.error("VirusTotal scan failed for hash %s: %s", file_hash, exc)
            raise SecurityScanError() from exc

        # -- 4. verdict ----------------------------------------------------
        if scan.verdict.value == "malicious":
            await self._log_scan(
                db, owner_id, validated.filename, validated.size, file_hash,
                ScanStatus.MALICIOUS, "; ".join(scan.reasons), scan,
            )
            await db.commit()
            logger.warning(
                "Rejected upload %s (hash %s): %s", validated.filename, file_hash, scan.reasons
            )
            raise MaliciousFileError(details={"scan": scan.to_log_detail()})

        if scan.verdict.value == "suspicious":
            await self._log_scan(
                db, owner_id, validated.filename, validated.size, file_hash,
                ScanStatus.SUSPICIOUS, "; ".join(scan.reasons), scan,
            )
            await db.commit()
            raise SuspiciousFileError(details={"scan": scan.to_log_detail()})
        # -- 5. safe storage -----------------------------------------------
        resource_id = uuid.uuid4()
        object_path = build_object_path(str(owner_id), str(resource_id), validated.filename)

        await self.storage.upload(object_path, file_bytes, validated.content_type)

        # -- 6. metadata row ------------------------------------------------
        resource = Resource(
            id=resource_id,
            owner_id=owner_id,
            title=payload.title,
            description=payload.description,
            subject=payload.subject,
            kulliyyah=payload.kulliyyah,
            category=payload.category,
            semester=payload.semester,
            tags=payload.tags,
            file_name=validated.filename,
            file_path=object_path,
            file_size=validated.size,
            file_type=validated.content_type,
            file_hash=file_hash,
            security_status=SecurityStatus.SAFE,
            publication_status=PublicationStatus.PROCESSING,
            ai_summary_status=AiSummaryStatus.PROCESSING,
        )
        db.add(resource)
        # Write the resource row before the audit row: security_logs references
        # it by foreign key. Relying on the ORM to infer that ordering is
        # fragile, so the dependency is made explicit with a flush.
        await db.flush()

        await self._log_scan(
            db, owner_id, validated.filename, validated.size, file_hash,
            ScanStatus.SAFE, "; ".join(scan.reasons), scan, resource_id=resource_id,
        )
        try:
            await db.commit()
        except Exception:
            # Metadata failed after the file landed: undo the storage write so
            # we never leave an orphaned, unreachable object behind.
            await db.rollback()
            await self.storage.delete(object_path)
            raise

        # -- 7-10. extraction, summarisation, publication --------------------
        summary_status, note = await self._process_document(db, resource, object_path)

        resource.publication_status = PublicationStatus.PUBLISHED
        await db.commit()
        await db.refresh(resource)

        logger.info(
            "Published resource %s (hash %s, summary=%s)",
            resource.id, file_hash, summary_status.value,
        )
        return UploadResult(
            resource=resource,
            scan=scan,
            summary_status=summary_status,
            extraction_note=note,
        )

    async def _process_document(
        self, db: AsyncSession, resource: Resource, object_path: str
    ) -> tuple[AiSummaryStatus, str | None]:
        """Steps 7-9. Never raises; the resource is published either way."""
        try:
            raw = await self.storage.download(object_path)
        except StorageError as exc:
            return self._record_ai_failure(db, resource, f"Could not read the stored file: {exc}")
        except Exception as exc:
            return self._record_ai_failure(db, resource, f"Unexpected read error: {type(exc).__name__}")

        extraction = extract_text(raw, self.settings)
        resource.page_count = extraction.page_count

        if not extraction.has_usable_text:
            reason = extraction.error or "No readable text was found."
            logger.info("Skipping summary for %s: %s", resource.id, reason)
            resource.ai_summary_status = AiSummaryStatus.SKIPPED
            resource.ai_summary_error = reason
            return AiSummaryStatus.SKIPPED, reason

        result: SummaryResult = await self.summarizer.summarize(extraction.text)

        if result.status is SummaryStatus.COMPLETED and result.is_usable:
            resource.ai_summary = result.summary
            resource.ai_keywords = result.keywords
            resource.ai_model = result.model
            resource.ai_summary_status = AiSummaryStatus.COMPLETED
            resource.ai_summary_error = result.error  # may note a fallback
            return AiSummaryStatus.COMPLETED, None

        if result.status is SummaryStatus.SKIPPED:
            resource.ai_summary_status = AiSummaryStatus.SKIPPED
            resource.ai_summary_error = result.error
            return AiSummaryStatus.SKIPPED, result.error

        # Failed: keep a short extract so the page still shows something useful.
        resource.ai_summary = first_sentences(extraction.text)
        resource.ai_keywords = []
        resource.ai_model = result.model
        resource.ai_summary_status = AiSummaryStatus.FAILED
        resource.ai_summary_error = result.error
        logger.warning("Summarisation failed for %s: %s", resource.id, result.error)
        return AiSummaryStatus.FAILED, result.error

    def _record_ai_failure(
        self, db: AsyncSession, resource: Resource, reason: str
    ) -> tuple[AiSummaryStatus, str]:
        resource.ai_summary_status = AiSummaryStatus.FAILED
        resource.ai_summary_error = reason
        return AiSummaryStatus.FAILED, reason

    async def _log_scan(
        self,
        db: AsyncSession,
        owner_id: uuid.UUID,
        filename: str,
        size: int,
        file_hash: str,
        status: ScanStatus,
        details: str,
        scan: ScanOutcome | None = None,
        resource_id: uuid.UUID | None = None,
    ) -> SecurityLog:
        entry = SecurityLog(
            resource_id=resource_id,
            user_id=owner_id,
            file_name=filename,
            file_size=size,
            file_hash=file_hash,
            scan_status=status,
            scan_result=scan.to_log_detail() if scan else None,
            virustotal_analysis_id=scan.analysis_id if scan else None,
            details=details,
        )
        db.add(entry)
        return entry

@dataclass
class UploadResult:
    resource: Resource
    scan: ScanOutcome
    summary_status: AiSummaryStatus
    extraction_note: str | None = None
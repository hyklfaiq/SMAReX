"""Resources: browse, search, upload, download, delete, retry summary."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, File, Form, Query, UploadFile
from sqlalchemy import asc, desc, func, or_, select

from app.api.deps import (
    CurrentUser,
    DbSession,
    Scanner,
    Storage,
    SummarizerDep,
    load_resource,
)
from app.core.config import get_settings
from app.core.exceptions import ConflictError, FileTooLargeError
from app.core.logging import get_logger
from app.models import DownloadHistory, PublicationStatus, Resource, SecurityStatus
from app.pipeline.upload_pipeline import UploadPipeline
from app.schemas import (
    DownloadResponse,
    Page,
    ResourceCreate,
    ResourceDetail,
    ResourceSummary,
)
from app.security.hashing import sha256_bytes
from app.security.permissions import (
    assert_can_download_resource,
    assert_can_modify_resource,
    assert_can_view_resource,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/resources", tags=["resources"])

SortOption = Literal["newest", "oldest", "rating", "downloads", "relevance"]


def _to_summary(resource: Resource) -> ResourceSummary:
    return ResourceSummary(**resource.to_summary_dict())


def _to_detail(resource: Resource, viewer_id: str | None) -> ResourceDetail:
    data = resource.to_summary_dict()
    data.update(
        file_name=resource.file_name,
        file_type=resource.file_type,
        page_count=resource.page_count,
        ai_summary=resource.ai_summary,
        ai_keywords=list(resource.ai_keywords or []),
        ai_model=resource.ai_model,
        ai_summary_error=resource.ai_summary_error,
        owner_id=str(resource.owner_id),
        is_owner=bool(viewer_id and str(resource.owner_id) == viewer_id),
    )
    return ResourceDetail(**data)


@router.get("", response_model=Page[ResourceSummary])
async def list_resources(
    db: DbSession,
    user: CurrentUser,
    q: str | None = Query(default=None, max_length=200, description="Search text"),
    kulliyyah: str | None = Query(default=None, max_length=120),
    subject: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=60),
    semester: str | None = Query(default=None, max_length=40),
    tag: str | None = Query(default=None, max_length=60),
    mine: bool = Query(default=False, description="Only resources I uploaded"),
    sort: SortOption = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=60),
):
    """Published + safe resources only. Owners can list their own with ``mine``."""
    filters = []

    if mine:
        filters.append(Resource.owner_id == uuid.UUID(user.id))
    else:
        filters.append(Resource.publication_status == PublicationStatus.PUBLISHED)
        filters.append(Resource.security_status == SecurityStatus.SAFE)

    if kulliyyah:
        filters.append(func.lower(Resource.kulliyyah) == kulliyyah.strip().lower())
    if subject:
        filters.append(func.lower(Resource.subject) == subject.strip().lower())
    if category:
        filters.append(func.lower(Resource.category) == category.strip().lower())
    if semester:
        filters.append(Resource.semester == semester.strip())
    if tag:
        filters.append(tag.strip().lower() == func.lower(func.any_(Resource.tags)))

    if q and q.strip():
        # Full-text first, with a LIKE fallback so partial words still match.
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Resource.search_vector.op("@@")(func.websearch_to_tsquery("simple", q)),
                Resource.title.ilike(pattern),
                Resource.description.ilike(pattern),
                Resource.subject.ilike(pattern),
            )
        )

    order = {
        "newest": desc(Resource.created_at),
        "oldest": asc(Resource.created_at),
        "rating": desc(Resource.rating_avg),
        "downloads": desc(Resource.download_count),
        "relevance": desc(Resource.created_at),
    }[sort]

    total = await db.scalar(select(func.count()).select_from(Resource).where(*filters)) or 0
    result = await db.execute(
        select(Resource).where(*filters).order_by(order).offset((page - 1) * page_size).limit(page_size)
    )
    resources = result.scalars().all()

    return Page[ResourceSummary].build(
        items=[_to_summary(r) for r in resources], total=total, page=page, page_size=page_size
    )
@router.get("/{resource_id}", response_model=ResourceDetail)
async def get_resource(
    resource_id: str,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
):
    """Details plus a short-lived signed URL when the file is downloadable."""
    resource = await load_resource(db, resource_id)
    assert_can_view_resource(user, resource)

    # The download link is issued by the dedicated endpoint, not pre-signed
    # here, so nothing about storage leaks into the details payload.
    return _to_detail(resource, user.id)


@router.post("", response_model=ResourceDetail, status_code=201)
async def upload_resource(
    db: DbSession,
    user: CurrentUser,
    scanner: Scanner,
    storage: Storage,
    summarizer: SummarizerDep,
    file: UploadFile = File(..., description="The PDF to share"),
    title: str = Form(..., min_length=3, max_length=300),
    description: str = Form("", max_length=8000),
    subject: str = Form(..., min_length=2, max_length=200),
    kulliyyah: str = Form(..., min_length=2, max_length=120),
    category: str = Form(..., min_length=2, max_length=60),
    semester: str | None = Form(None, max_length=40),
    tags: str | None = Form(None, description="Comma-separated keywords"),
):
    """The full pipeline: validate -> hash -> VirusTotal -> store -> extract ->
    summarise -> publish.

    Returns 201 with the published resource, or 4xx if the file is rejected.
    """
    settings = get_settings()

    # Read the upload into memory: VirusTotal needs the bytes and our size cap
    # is small enough that buffering is safe.
    file_bytes = await file.read()
    if len(file_bytes) > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"Files must be smaller than {settings.max_upload_mb} MB."
        )

    payload = ResourceCreate(
        title=title,
        description=description,
        subject=subject,
        kulliyyah=kulliyyah,
        category=category,
        semester=semester,
        tags=[t for t in (tags or "").split(",") if t.strip()],
    )

    # Cheap duplicate guard before we spend a VirusTotal call on the same file.
    duplicate_hash = sha256_bytes(file_bytes)
    duplicate = await db.scalar(
        select(Resource).where(
            Resource.file_hash == duplicate_hash,
            Resource.publication_status != PublicationStatus.DELETED,
        )
    )
    if duplicate is not None:
        raise ConflictError(
            "This file has already been uploaded.",
            details={"resource_id": str(duplicate.id)},
        )

    pipeline = UploadPipeline(scanner, storage, summarizer, settings)
    result = await pipeline.run(
        db=db,
        owner_id=uuid.UUID(user.id),
        payload=payload,
        file_bytes=file_bytes,
        raw_filename=file.filename,
        content_type=file.content_type,
    )

    detail = _to_detail(result.resource, user.id)
    if result.extraction_note:
        detail.ai_summary_error = result.extraction_note
    return detail


@router.get("/{resource_id}/download", response_model=DownloadResponse)
async def download_resource(
    resource_id: str,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
):
    """Authorise, record the download, and return a short-lived signed URL."""
    resource = await load_resource(db, resource_id)
    assert_can_download_resource(user, resource)

    db.add(DownloadHistory(resource_id=resource.id, user_id=uuid.UUID(user.id)))
    resource.download_count += 1
    await db.commit()

    url = await storage.create_signed_url(resource.file_path)
    return DownloadResponse(
        url=url,
        file_name=resource.file_name,
        expires_in=get_settings().signed_url_ttl_seconds,
    )


@router.delete("/{resource_id}")
async def delete_resource(
    resource_id: str,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
):
    """Owners and admins only. Removes the stored file, then the row."""
    resource = await load_resource(db, resource_id)
    assert_can_modify_resource(user, resource)

    path = resource.file_path
    db.delete(resource)
    await db.commit()
    await storage.delete(path)
    return {"message": "Resource deleted."}


@router.post("/{resource_id}/summary/retry", response_model=ResourceDetail)
async def retry_summary(
    resource_id: str,
    db: DbSession,
    user: CurrentUser,
    storage: Storage,
    summarizer: SummarizerDep,
):
    """Re-run extraction + summarisation for a resource whose summary failed."""
    resource = await load_resource(db, resource_id)
    assert_can_modify_resource(user, resource)

    pipeline = UploadPipeline(_NoopScanner(), storage, summarizer, get_settings())
    await pipeline._process_document(db, resource, resource.file_path)
    await db.commit()
    await db.refresh(resource)
    return _to_detail(resource, user.id)


class _NoopScanner:
    """The retry path re-processes text only; it must not rescan."""

    def __init__(self) -> None:
        self.scanner = None

    async def scan_bytes(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("The scanner is not used on the retry path.")
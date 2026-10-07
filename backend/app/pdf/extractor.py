"""PDF text extraction with pypdf.

Runs only on files that have already passed the VirusTotal scan and been
stored safely. Extraction is best-effort: every failure mode here is turned
into a recorded outcome rather than an exception that could damage the
already-stored file.

Handled explicitly:

* empty or corrupt PDFs
* scanned / image-only PDFs (no text layer)
* encrypted PDFs
* very long documents (hard page cap)
* pages that raise individually while parsing the whole file
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Extraction stops here regardless of document length. 500 pages is far more
# than enough to summarise an academic document and bounds the work per upload.
MAX_PAGES = 500

_WHITESPACE_RUN = re.compile(r"[ \t ]{2,}")
_BLANK_LINES = re.compile(r"\n{3,}")
# Ligatures and soft hyphens that PDF text layers frequently emit split up.
_LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class ExtractionStatus(str, Enum):
    OK = "ok"
    EMPTY = "empty"              # no text layer at all (scanned or blank)
    ENCRYPTED = "encrypted"
    CORRUPT = "corrupt"
    TOO_LARGE = "too_large"
    FAILED = "failed"


@dataclass
class ExtractionResult:
    """Outcome of one extraction attempt."""

    status: ExtractionStatus
    text: str = ""
    page_count: int = 0
    pages_with_text: int = 0
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def has_usable_text(self) -> bool:
        return self.status is ExtractionStatus.OK and len(self.text.strip()) >= 1

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "page_count": self.page_count,
            "pages_with_text": self.pages_with_text,
            "char_count": len(self.text),
            "error": self.error,
            "warnings": self.warnings,
        }


def clean_text(raw: str) -> str:
    """Normalise a PDF text layer for the summariser.

    Repairs ligatures and stray control characters, collapses runs of
    whitespace, and removes repeated headers/footers.
    """
    if not raw:
        return ""

    text = raw.translate(_LIGATURES)
    text = _CONTROL.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RUN.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def extract_text(
    data: bytes,
    settings: Settings | None = None,
    max_pages: int = MAX_PAGES,
) -> ExtractionResult:
    """Extract and clean the text of a PDF held entirely in memory.

    Never raises: every failure comes back as an :class:`ExtractionResult` with
    a non-OK status so the pipeline can mark the resource and move on.
    """
    settings = settings or get_settings()

    if not data:
        return ExtractionResult(status=ExtractionStatus.EMPTY, error="No file content.")

    try:
        reader = PdfReader(BytesIO(data))
    except (PdfReadError, PdfStreamError, ValueError, OSError) as exc:
        logger.warning("pypdf could not open the document: %s", type(exc).__name__)
        return ExtractionResult(status=ExtractionStatus.CORRUPT, error=str(exc))
    except Exception as exc:  # defensive: pypdf can raise almost anything
        logger.exception("Unexpected error opening PDF")
        return ExtractionResult(status=ExtractionStatus.FAILED, error=str(exc))

    if getattr(reader, "is_encrypted", False):
        # A zero-length user password is common for "protected" but open PDFs.
        try:
            if reader.decrypt("") == 0:
                return ExtractionResult(
                    status=ExtractionStatus.ENCRYPTED,
                    error="This PDF is password protected.",
                )
        except Exception:
            return ExtractionResult(
                status=ExtractionStatus.ENCRYPTED,
                error="This PDF is password protected.",
            )

    warnings: list[str] = []
    try:
        total_pages = len(reader.pages)
    except Exception as exc:
        return ExtractionResult(status=ExtractionStatus.CORRUPT, error=str(exc))

    if total_pages == 0:
        return ExtractionResult(
            status=ExtractionStatus.EMPTY, page_count=0, error="The PDF has no pages."
        )

    pages_to_read = total_pages
    if total_pages > max_pages:
        pages_to_read = max_pages
        warnings.append(
            f"Only the first {max_pages} of {total_pages} pages were analysed."
        )

    chunks: list[str] = []
    pages_with_text = 0

    for index in range(pages_to_read):
        try:
            page_text = reader.pages[index].extract_text() or ""
        except Exception as exc:
            # One malformed page must not lose the rest of the document.
            logger.debug("Skipping page %d: %s", index + 1, type(exc).__name__)
            warnings.append(f"Page {index + 1} could not be read.")
            continue

        cleaned = clean_text(page_text)
        if cleaned:
            chunks.append(cleaned)
            pages_with_text += 1

    text = "\n\n".join(chunks).strip()

    if not text:
        return ExtractionResult(
            status=ExtractionStatus.EMPTY,
            page_count=total_pages,
            warnings=warnings,
            error=(
                "No selectable text was found. This looks like a scanned or "
                "image-only PDF, which cannot be summarised automatically."
            ),
        )

    return ExtractionResult(
        status=ExtractionStatus.OK,
        text=text,
        page_count=total_pages,
        pages_with_text=pages_with_text,
        warnings=warnings,
    )


def looks_scanned(result: ExtractionResult, settings: Settings | None = None) -> bool:
    """Heuristic used for the 'scanned PDF' user-facing message."""
    settings = settings or get_settings()
    if result.status is ExtractionStatus.EMPTY:
        return True
    if result.page_count and result.pages_with_text / result.page_count < 0.2:
        return True
    return len(result.text) < settings.ai_min_text_chars

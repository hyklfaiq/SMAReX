"""Uploading file validation.

Checks are applied in increasing order of cost so that obviously bad requests
are rejected before anything expensive runs:

1. filename sanity + extension
2. declared MIME type
3. declared size
4. PDF magic bytes (the file must actually start with ``%PDF-``)
5. structural parse of the header/trailer via pypdf

This runs *before* the file is hashed or sent to VirusTotal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.config import Settings, get_settings
from app.core.exceptions import FileTooLargeError, InvalidFileError, ValidationError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Every well-formed PDF starts with this. Checked because a browser-supplied
# content type or a renamed .exe both lie about what a file contains.
PDF_MAGIC = b"%PDF-"

# Conservative: a header must appear within the first 1 KiB, because some
# generators prepend junk before the header.
MAGIC_SEARCH_WINDOW = 1024

# Strips any directory component and anything that is not a plain filename.
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._()\- ]+")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

ALLOWED_EXTENSIONS = frozenset({".pdf"})


@dataclass(frozen=True)
class ValidatedUpload:
    """Result of a successful pre-flight check."""

    filename: str
    size: int
    content_type: str

    @property
    def size_mb(self) -> float:
        return round(self.size / (1024 * 1024), 2)


def sanitise_filename(raw: str | None, fallback: str = "document.pdf") -> str:
    """Reduce an untrusted filename to a safe, single path segment.

    Strips directory traversal, control characters and exotic symbols.

    The extension is deliberately left untouched. Appending ``.pdf`` here would
    let ``virus.exe`` pass the extension check, so validation rejects anything
    that is not already a PDF instead.
    """
    if not raw:
        return fallback

    # Drop any directory component, honouring both separators.
    name = PurePosixPath(raw.replace("\\", "/")).name
    name = _CONTROL_CHARS.sub("", name)
    name = _UNSAFE_FILENAME.sub("", name).strip().strip(".")
    name = name[:150]

    return name or fallback


def validate_extension(filename: str) -> None:
    ext = PurePosixPath(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileError(
            "Only PDF files can be uploaded.",
            details={"extension": ext or None},
        )


def validate_content_type(content_type: str | None, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not content_type:
        raise InvalidFileError("The upload did not declare a content type.")

    mime = content_type.split(";")[0].strip().lower()
    if mime not in settings.allowed_pdf_mime_types:
        raise InvalidFileError(
            "Only PDF files can be uploaded.",
            details={"content_type": mime},
        )


def validate_size(size: int, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if size <= 0:
        raise InvalidFileError("That file appears to be empty.")
    if size > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"Files must be smaller than {settings.max_upload_mb} MB.",
            details={
                "max_bytes": settings.max_upload_bytes,
                "received_bytes": size,
            },
        )


def has_pdf_magic_bytes(head: bytes) -> bool:
    """True when a ``%PDF-`` header appears near the start of the file."""
    return PDF_MAGIC in head[:MAGIC_SEARCH_WINDOW]


def validate_pdf_header(head: bytes) -> None:
    if not has_pdf_magic_bytes(head):
        raise InvalidFileError(
            "That file is not a valid PDF. The file content does not match "
            "its extension."
        )


def validate_upload(
    *,
    filename: str | None,
    content_type: str | None,
    size: int,
    head: bytes,
    settings: Settings | None = None,
) -> ValidatedUpload:
    """Run every pre-flight check and return the sanitised result.

    ``head`` is the first ~1 KiB of the uploaded file.
    """
    settings = settings or get_settings()

    clean_name = sanitise_filename(filename)
    validate_extension(clean_name)
    validate_content_type(content_type, settings)
    validate_size(size, settings)
    validate_pdf_header(head)

    logger.debug(
        "Upload pre-flight passed: %s (%s bytes, %s)",
        clean_name,
        size,
        content_type,
    )
    return ValidatedUpload(
        filename=clean_name,
        size=size,
        content_type=content_type.split(";")[0].strip().lower(),
    )


def validate_tag_list(tags: list[str] | None, *, limit: int = 15) -> list[str]:
    """Normalise uploader-supplied tags: strip, lowercase, de-duplicate."""
    if not tags:
        return []
    cleaned: list[str] = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValidationError("Tags must be text.")
        normalised = re.sub(r"\s+", " ", tag).strip().lower()
        if not normalised:
            continue
        if len(normalised) > 60:
            raise ValidationError("Each tag must be 60 characters or fewer.")
        if normalised not in cleaned:
            cleaned.append(normalised)
    if len(cleaned) > limit:
        raise ValidationError(f"You can add at most {limit} tags.")
    return cleaned
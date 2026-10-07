"""SHA-256 hashing, used both as the dedupe key and as the VirusTotal lookup key."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024  # 1 MiB -- keeps memory flat for large uploads


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Stream a file through SHA-256 without loading it into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


async def sha256_stream(stream) -> str:
    """Hash an async file-like object (the UploadFile stream).

    Returns the hex digest and leaves the stream rewound to position 0 so the
    same bytes can subsequently be re-sent to storage or VirusTotal.
    """
    digest = hashlib.sha256()
    while chunk := await stream.read(_CHUNK):
        digest.update(chunk)
    await stream.seek(0)
    return digest.hexdigest()


def sha256_and_count(stream) -> tuple[str, int]:
    """Hash a synchronous binary stream, returning ``(hexdigest, byte_count)``."""
    digest = hashlib.sha256()
    total = 0
    while chunk := stream.read(_CHUNK):
        digest.update(chunk)
        total += len(chunk)
    if hasattr(stream, "seek"):
        stream.seek(0)
    return digest.hexdigest(), total
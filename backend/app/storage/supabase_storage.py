"""Supabase Storage access for uploaded PDFs.

The bucket is private. Nothing is fetched through the public CDN endpoint;
every download is authorised by the backend and handed to the browser as a
short-lived signed URL.

Uses the Storage REST API over httpx rather than the SDK, so the service-role
key never has to be shared with any other component.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class StoredObject:
    path: str
    bucket: str
    size: int


def build_object_path(owner_id: str, resource_id: str, filename: str) -> str:
    """``{owner}/{resource}/{file}`` -- the first segment is the owner, which is
    exactly what the storage RLS policies key off."""
    return f"{owner_id}/{resource_id}/{filename}"


class SupabaseStorage:
    """Client for the Storage REST API. Injectable for tests."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None

    # -- plumbing ------------------------------------------------------------
    @property
    def bucket(self) -> str:
        return self.settings.storage_bucket

    def _storage_url(self, path: str = "") -> str:
        base = self.settings.supabase_url.rstrip("/")
        encoded = quote(path, safe="/")
        return f"{base}/storage/v1/object/{self.bucket}/{encoded}".rstrip("/")

    def _headers(self, **extra: str) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "apikey": self.settings.supabase_service_role_key,
        }
        headers.update(extra)
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            # Large uploads: generous read timeout, bounded connect timeout.
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0, connect=10.0),
                limits=httpx.Limits(max_connections=10),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def _require_key(self) -> None:
        if not self.settings.supabase_service_role_key:
            raise StorageError(
                "File storage is not configured on the server.",
                code="storage_not_configured",
            )

    # -- operations ----------------------------------------------------------
    async def upload(
        self,
        path: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> StoredObject:
        """Store the file. Raises on any failure so the caller can roll back."""
        self._require_key()
        client = await self._get_client()

        try:
            response = await client.post(
                self._storage_url(path),
                content=data,
                headers=self._headers(
                    **{"Content-Type": content_type, "x-upsert": "false"}
                ),
            )
        except httpx.HTTPError as exc:
            logger.error("Storage upload transport failure for %s: %s", path, type(exc).__name__)
            raise StorageError("The file could not be stored. Please try again.") from exc

        if response.status_code >= 400:
            logger.error("Storage upload failed for %s (HTTP %s)", path, response.status_code)
            raise StorageError("The file could not be stored. Please try again.")

        logger.info("Stored object %s/%s (%d bytes)", self.bucket, path, len(data))
        return StoredObject(path=path, bucket=self.bucket, size=len(data))

    async def create_signed_url(self, path: str, expires_in: int | None = None) -> str:
        """Time-limited download URL handed to the browser after authorisation."""
        self._require_key()
        client = await self._get_client()
        ttl = expires_in or self.settings.signed_url_ttl_seconds

        base = self.settings.supabase_url.rstrip("/")
        url = f"{base}/storage/v1/object/sign/{self.bucket}/{quote(path, safe='/')}"

        try:
            response = await client.post(url, json={"expiresIn": ttl}, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.error("Signed URL request failed: %s", type(exc).__name__)
            raise StorageError("The download link could not be created.") from exc

        if response.status_code >= 400:
            raise StorageError("The download link could not be created.")

        payload = response.json()
        signed_path = payload.get("signedURL") or payload.get("signedUrl")
        if not signed_path:
            raise StorageError("The download link could not be created.")

        # The API returns a path; prefix it with the project URL.
        if signed_path.startswith("http"):
            return signed_path
        return f"{base}{signed_path.lstrip('/')}"

    async def download(self, path: str) -> bytes:
        """Server-side read. Used by the AI step, never exposed to clients."""
        self._require_key()
        client = await self._get_client()

        try:
            response = await client.get(self._storage_url(path), headers=self._headers())
        except httpx.HTTPError as exc:
            raise StorageError("The stored file could not be read.") from exc

        if response.status_code == 404:
            raise StorageError(
                "The stored file is missing.", code="object_missing", status_code=404
            )
        if response.status_code >= 400:
            raise StorageError("The stored file could not be read.")
        return response.content

    async def delete(self, path: str) -> bool:
        """Best-effort removal. Used on rollback and by admin moderation."""
        self._require_key()
        client = await self._get_client()

        try:
            response = await client.delete(self._storage_url(path), headers=self._headers())
        except httpx.HTTPError as exc:
            logger.warning("Storage delete failed for %s: %s", path, type(exc).__name__)
            return False

        if response.status_code == 404:
            return False
        if response.status_code >= 400:
            logger.warning("Storage delete returned HTTP %s for %s", response.status_code, path)
            return False

        logger.info("Deleted object %s/%s", self.bucket, path)
        return True

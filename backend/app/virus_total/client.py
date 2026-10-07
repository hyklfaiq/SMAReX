"""VirusTotal integration.

VirusTotal is an external file-analysis service. SMAReX submits the upload to
its ``/files`` endpoint, which returns an analysis id, then polls
``/analyses/{id}`` until the analysis completes. The verdict is read from the
``stats`` object, whose counters reflect how many of the participating
security vendors classified the file in each way:

    {"malicious": 0, "suspicious": 0, "undetected": 62, "harmless": 0, ...}

SMAReX does not assert what any individual vendor's detection technique is;
it only aggregates the published ``stats`` counters into a single accept /
reject decision, configurable through the settings.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import SecurityScanError, UpstreamServiceError
from app.core.logging import get_logger
from app.models import ScanStatus, SecurityStatus

logger = get_logger(__name__)

# VirusTotal returns 429 when the free tier quota (4 requests/min) is exceeded.
_RATE_LIMIT_STATUS = 429


class VirusTotalError(UpstreamServiceError):
    code = "virustotal_error"
    message = "The security scanner could not be reached."


class VirusTotalNotConfigured(VirusTotalError):
    code = "virustotal_not_configured"
    message = "The security scanner has not been configured."


class ScanVerdict(str, Enum):
    SAFE = "safe"
    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"


@dataclass
class ScanOutcome:
    """Aggregated result of one VirusTotal analysis."""

    verdict: ScanVerdict
    status: SecurityStatus
    scan_status: ScanStatus
    stats: dict[str, int] = field(default_factory=dict)
    analysis_id: str | None = None
    permalink: str | None = None
    detection_ratio: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def is_acceptable(self) -> bool:
        return self.verdict is ScanVerdict.SAFE

    def to_log_detail(self) -> dict[str, Any]:
        """Compact payload persisted in ``security_logs.scan_result``."""
        return {
            "verdict": self.verdict.value,
            "analysis_id": self.analysis_id,
            "permalink": self.permalink,
            "detection_ratio": self.detection_ratio,
            "stats": self.stats,
            "reasons": self.reasons,
        }


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
class VirusTotalClient:
    """Thin async wrapper over the two endpoints SMAReX needs.

    Injectable ``httpx.AsyncClient`` so tests can substitute a transport.
    """

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
    def _headers(self) -> dict[str, str]:
        return {"x-apikey": self.settings.virustotal_api_key, "accept": "application/json"}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "VirusTotalClient":
        await self._get_client()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    def _require_key(self) -> None:
        if not self.settings.virustotal_api_key:
            raise VirusTotalNotConfigured()

    # -- API calls -----------------------------------------------------------
    async def upload_file(self, file_bytes: bytes, filename: str) -> str:
        """POST /files -- returns the analysis id for the queued scan."""
        self._require_key()

        if len(file_bytes) > self.settings.virustotal_max_file_bytes:
            raise VirusTotalError(
                "The file is too large for the security scanner.",
                code="file_too_large_for_scanner",
                status_code=413,
            )

        client = await self._get_client()
        url = f"{self.settings.virustotal_base_url.rstrip('/')}/files"

        try:
            response = await client.post(
                url,
                headers=self._headers,
                files={"file": (filename, file_bytes, "application/pdf")},
            )
        except httpx.HTTPError as exc:
            logger.error("VirusTotal upload failed: %s", type(exc).__name__)
            raise VirusTotalError(details={"stage": "upload"}) from exc

        self._raise_for_status(response, "upload")

        payload = self._json(response, "upload")
        data = payload.get("data") or {}
        analysis_id = data.get("id")
        if not analysis_id:
            raise VirusTotalError("The security scanner returned an unexpected response.")
        return str(analysis_id)

    async def get_analysis(self, analysis_id: str) -> dict[str, Any]:
        """GET /analyses/{id} -- the analysis object, queued or completed."""
        self._require_key()
        client = await self._get_client()
        url = f"{self.settings.virustotal_base_url.rstrip('/')}/analyses/{analysis_id}"

        try:
            response = await client.get(url, headers=self._headers)
        except httpx.HTTPError as exc:
            logger.error("VirusTotal analysis poll failed: %s", type(exc).__name__)
            raise VirusTotalError(details={"stage": "analysis"}) from exc

        self._raise_for_status(response, "analysis")
        return self._json(response, "analysis")

    async def get_file_report(self, file_hash: str) -> dict[str, Any] | None:
        """GET /files/{hash} -- existing report for a hash we may already know."""
        self._require_key()
# -- helpers -------------------------------------------------------------
    def _raise_for_status(self, response: httpx.Response, stage: str) -> None:
        if response.status_code < 400:
            return

        if response.status_code == _RATE_LIMIT_STATUS:
            logger.warning("VirusTotal rate limit hit during %s", stage)
            raise VirusTotalError(
                "The security scanner is busy right now. Please try again shortly.",
                code="virustotal_rate_limited",
                status_code=429,
            )
        if response.status_code in (401, 403):
            logger.error("VirusTotal rejected our API key during %s", stage)
            raise VirusTotalError(
                code="virustotal_unauthorised",
                status_code=502,
            )
        raise VirusTotalError(
            details={"stage": stage, "upstream_status": response.status_code}
        )

    @staticmethod
    def _json(response: httpx.Response, stage: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise VirusTotalError(
                "The security scanner returned an unreadable response.",
                details={"stage": stage},
            ) from exc
        if not isinstance(payload, dict):
            raise VirusTotalError(details={"stage": stage})
        return payload

    # -- verdict -------------------------------------------------------------
    def classify(self, analysis: dict[str, Any]) -> ScanOutcome:
        """Turn a completed analysis object into an accept / reject decision."""
        data = analysis.get("data") or {}
        attributes = data.get("attributes") or {}
        raw_stats = attributes.get("stats") or {}

        stats = {
            key: _coerce_int(value)
            for key, value in raw_stats.items()
            if key in {"malicious", "suspicious", "undetected", "harmless",
                       "timeout", "failure", "type_unsupported", "confirmed_timeout"}
        }
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)

        reasons: list[str] = []
        if malicious >= self.settings.virustotal_reject_on_malicious:
            verdict = ScanVerdict.MALICIOUS
            status = SecurityStatus.MALICIOUS
            reasons.append(
                f"{malicious} security vendor(s) classified this file as malicious."
            )
        elif suspicious >= self.settings.virustotal_reject_on_suspicious:
            verdict = ScanVerdict.SUSPICIOUS
            status = SecurityStatus.SUSPICIOUS
            reasons.append(
                f"{suspicious} security vendor(s) raised a suspicious flag."
            )
        else:
            verdict = ScanVerdict.SAFE
            status = SecurityStatus.SAFE
            reasons.append(
                "No security vendor reported this file as malicious or suspicious."
            )

        malicious_total = malicious + suspicious
        ratio = (
            f"{malicious_total}/{malicious_total + stats.get('harmless', 0) + stats.get('undetected', 0)}"
            if malicious_total or stats.get("harmless") or stats.get("undetected")
            else None
        )

        logger.info(
            "VirusTotal verdict=%s malicious=%d suspicious=%d",
            verdict.value, malicious, suspicious,
        )

        return ScanOutcome(
            verdict=verdict,
            status=status,
            scan_status=ScanStatus(verdict.value),
            stats=stats,
            analysis_id=str(data.get("id")) if data.get("id") else None,
            permalink=self._permalink_from(attributes, data.get("id")),
            detection_ratio=ratio,
            reasons=reasons,
        )

    @staticmethod
    def _permalink_from(attributes: dict[str, Any], analysis_id: Any) -> str | None:
        if isinstance(attributes.get("permalink"), str):
            return attributes["permalink"]
        return f"https://www.virustotal.com/gui/file-analysis/{analysis_id}" if analysis_id else None

    # -- orchestration -------------------------------------------------------
    async def wait_for_analysis(self, analysis_id: str) -> dict[str, Any]:
        """Poll until VirusTotal reports the analysis as ``completed``."""
        delay = self.settings.virustotal_poll_interval_seconds
        attempts = self.settings.virustotal_poll_max_attempts

        for attempt in range(1, attempts + 1):
            payload = await self.get_analysis(analysis_id)
            status = str((payload.get("data") or {}).get("attributes", {}).get("status", ""))
            if status == "completed":
                return payload
            if attempt < attempts:
                await asyncio.sleep(delay)
                delay = min(delay * 1.2, 15.0)

        raise VirusTotalError(
            "The security scan did not finish in time.",
            code="virustotal_timeout",
            status_code=504,
        )

    async def scan_bytes(self, file_bytes: bytes, filename: str) -> ScanOutcome:
        """Upload, wait for completion, and classify. The full scan path."""
        analysis_id = await self.upload_file(file_bytes, filename)
        analysis = await self.wait_for_analysis(analysis_id)
        return self.classify(analysis)

    async def scan_by_hash(self, file_hash: str, settings: Settings | None = None) -> ScanOutcome | None:
        """Reuse an existing VirusTotal report instead of re-uploading.

        Returns ``None`` when the hash is unknown to VirusTotal, in which case
        the caller should fall back to :meth:`scan_bytes`.
        """
        report = await self.get_file_report(file_hash)
        if not report:
            return None
        return self.classify(report)
        client = await self._get_client()
        url = f"{self.settings.virustotal_base_url.rstrip('/')}/files/{file_hash}"

        try:
            response = await client.get(url, headers=self._headers)
        except httpx.HTTPError as exc:
            logger.error("VirusTotal file report failed: %s", type(exc).__name__)
            return None

        if response.status_code == 404:
            return None
        self._raise_for_status(response, "file_report")
        return self._json(response, "file_report")
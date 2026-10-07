"""Summarisation via the hosted Hugging Face Inference API.

Default provider: no model download, no GPU, small deployment footprint. The
API call is per chunk; the partial results are combined into one summary.

Set ``HUGGINGFACE_API_KEY`` to raise the rate limit. A missing key still works
for public models at a lower quota.
"""

from __future__ import annotations

import httpx

from app.ai.base import (
    SummarizationError,
    Summarizer,
    SummaryResult,
    SummaryStatus,
)
from app.ai.preprocess import chunk_text, combine_summaries, extract_keywords
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_TOKENS = 220
MIN_LENGTH = 40


class HuggingFaceInferenceSummarizer(Summarizer):
    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_name = self.settings.ai_model
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.huggingface_timeout_seconds)
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.huggingface_api_key:
            headers["Authorization"] = f"Bearer {self.settings.huggingface_api_key}"
        return headers

    def _endpoint(self) -> str:
        return f"{self.settings.huggingface_api_url.rstrip('/')}/{self.model_name}"

    @staticmethod
    def _parse_payload(payload: object) -> str:
        """The endpoint returns [{"summary_text": "..."}] for this model."""
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                for key in ("summary_text", "generated_text", "text"):
                    value = first.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        if isinstance(payload, dict):
            error = payload.get("error")
            if error:
                raise SummarizationError(
                    str(error), provider="huggingface_inference_api"
                )
        raise SummarizationError(
            "The summarisation service returned an unexpected response.",
            provider="huggingface_inference_api",
        )

    async def _summarize_chunk(self, text: str) -> str:
        client = await self._get_client()
        body = {
            "inputs": text,
            "parameters": {
                "max_length": MAX_TOKENS,
                "min_length": MIN_LENGTH,
                "do_sample": False,
                "truncation": True,
            },
            "options": {"wait_for_model": True},
        }

        try:
            response = await client.post(self._endpoint(), json=body, headers=self._headers())
        except httpx.HTTPError as exc:
            raise SummarizationError(
                f"Summarisation request failed: {type(exc).__name__}",
                provider="huggingface_inference_api",
            ) from exc

        # 503 is Hugging Face's "model is still loading" signal.
        if response.status_code == 503:
            raise SummarizationError(
                "The summarisation model is still loading. Try again shortly.",
                provider="huggingface_inference_api",
            )
        if response.status_code in (401, 403):
            raise SummarizationError(
                "The summarisation service rejected our credentials.",
                provider="huggingface_inference_api",
            )
        if response.status_code == 429:
            raise SummarizationError(
                "The summarisation service is rate limiting us. Try again shortly.",
                provider="huggingface_inference_api",
            )
        if response.status_code >= 400:
            raise SummarizationError(
                f"Summarisation failed with status {response.status_code}.",
                provider="huggingface_inference_api",
            )

        return self._parse_payload(response.json())

    async def summarize(self, text: str) -> SummaryResult:
        text = (text or "").strip()
        if not text:
            return SummaryResult(status=SummaryStatus.SKIPPED, model=self.model_name)

        chunks = chunk_text(text, self.settings)
        if not chunks:
            return SummaryResult(status=SummaryStatus.SKIPPED, model=self.model_name)

        logger.info("Summarising %d chunk(s) with %s", len(chunks), self.model_name)

        partials: list[str] = []
        try:
            # Sequential: keeps rate-limit pressure predictable and the log
            # readable. Use asyncio.gather if throughput matters more.
            for chunk in chunks:
                partials.append(await self._summarize_chunk(chunk.text))
        except SummarizationError as exc:
            logger.warning("Hugging Face summarisation failed: %s", exc)
            return SummaryResult(
                status=SummaryStatus.FAILED,
                model=self.model_name,
                chunk_count=len(chunks),
                error=str(exc),
            )

        summary = combine_summaries(partials)
        if not summary.strip():
            return SummaryResult(
                status=SummaryStatus.FAILED,
                model=self.model_name,
                chunk_count=len(chunks),
                error="The model returned an empty summary.",
            )

        return SummaryResult(
            status=SummaryStatus.COMPLETED,
            summary=summary,
            keywords=extract_keywords(text, self.settings),
            model=self.model_name,
            chunk_count=len(chunks),
        )

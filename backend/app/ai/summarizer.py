"""Summarisation provider selection.

SMAReX uses one provider: the hosted Hugging Face Inference API. It needs no
model download and no GPU, which keeps the deployment simple. Set
``AI_ENABLED=false`` to turn summarisation off entirely.
"""

from __future__ import annotations

from app.ai.base import Summarizer, SummaryResult, SummaryStatus
from app.ai.inference_api import HuggingFaceInferenceSummarizer
from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DisabledSummarizer(Summarizer):
    """Used when summarisation is switched off. Marks summaries as skipped."""

    model_name = "none"

    async def summarize(self, text: str) -> SummaryResult:
        return SummaryResult(
            status=SummaryStatus.SKIPPED,
            model=self.model_name,
            error="Automatic summarisation is disabled on this server.",
        )


def get_summarizer(settings: Settings | None = None) -> Summarizer:
    settings = settings or get_settings()
    if not settings.ai_enabled:
        logger.info("AI summarisation is disabled")
        return DisabledSummarizer()
    return HuggingFaceInferenceSummarizer(settings)
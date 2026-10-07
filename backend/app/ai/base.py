"""Provider-agnostic summarisation contract.

Two implementations exist -- the Hugging Face Inference API (default) and a
local ``transformers`` model -- and both return the same
:class:`SummaryResult`, so the pipeline is identical either way.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from enum import Enum


class SummaryStatus(str, Enum):
    COMPLETED = "completed"
    SKIPPED = "skipped"     # nothing to summarise (empty / scanned PDF)
    FAILED = "failed"


@dataclass
class SummaryResult:
    """What the AI stage produced."""

    status: SummaryStatus
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    model: str | None = None
    chunk_count: int = 0
    error: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.status is SummaryStatus.COMPLETED and bool(self.summary.strip())


class SummarizationError(Exception):
    """Raised by providers. Caught and recorded by the pipeline, never fatal."""

    def __init__(self, message: str, *, provider: str = "unknown") -> None:
        self.provider = provider
        super().__init__(message)


class Summarizer(abc.ABC):
    """Common interface for every summarisation backend."""

    #: Recorded on ``resources.ai_model`` so a summary can be traced to a model.
    model_name: str = "unknown"

    @abc.abstractmethod
    async def summarize(self, text: str) -> SummaryResult:
        """Summarise already-cleaned document text."""

    async def aclose(self) -> None:
        """Release any provider resources. Safe to call more than once."""
        return None
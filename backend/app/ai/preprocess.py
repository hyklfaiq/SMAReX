"""Text preprocessing: chunking for long documents and keyword extraction.

Abstractive models such as ``facebook/bart-large-cnn`` accept roughly 1024
tokens of input, so anything longer must be split. Each chunk is summarised
separately and the partial summaries are combined, which is more robust than
blindly truncating a thesis to its first page.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Academic filler words that carry no topical signal in a keyword list.
STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren't as at be because
    been before being below between both but by can cannot could couldn't did didn't
    do does doesn't doing don't down during each few for from further had hadn't has
    hasn't have haven't having he her here hers herself him himself his how i if in
    into is isn't it its itself let's me more most mustn't my myself no nor not of
    off on once only or other ought our ours ourselves out over own same shan't she
    should shouldn't so some such than that the their theirs them themselves then
    there these they this those through to too under until up very was wasn't we
    were weren't what when where which while who whom why with won't would wouldn't
    you your yours yourself yourselves also may might must shall will upon within
    without therefore thus hence whereas while et al fig figure table section
    """.split()
)

# Frequent academic boilerplate that should never become a "keyword".
_GENERIC = frozenset(
    {"study", "research", "paper", "results", "method", "methods", "using", "based",
     "analysis", "data", "introduction", "conclusion", "however", "therefore",
     "furthermore", "overall", "various", "different", "important", "include"}
)

_WORD = re.compile(r"[A-Za-z][A-Za-z\-']{2,}")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass
class Chunk:
    index: int
    text: str


def chunk_text(
    text: str,
    settings: Settings | None = None,
    max_chars: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Split long text into overlapping windows sized for the model.

    Splits on sentence boundaries where possible so a chunk never starts
    mid-sentence; falls back to a hard character cut when a single sentence is
    longer than the window.
    """
    settings = settings or get_settings()
    max_chars = max_chars or settings.ai_max_input_chars
    overlap = settings.ai_chunk_overlap_chars if overlap is None else overlap
    max_chars = max(max_chars, 200)
    overlap = min(overlap, max_chars // 2)

    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [Chunk(index=0, text=text)]

    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    if not sentences:
        sentences = [text]

    chunks: list[Chunk] = []
    current = ""

    for sentence in sentences:
        # A single over-long sentence is hard-split.
        while len(sentence) > max_chars:
            if current:
                chunks.append(Chunk(index=len(chunks), text=current.strip()))
                current = ""
            chunks.append(Chunk(index=len(chunks), text=sentence[:max_chars]))
            sentence = sentence[max_chars - overlap:]

        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip()
        else:
            if current:
                chunks.append(Chunk(index=len(chunks), text=current.strip()))
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {sentence}".strip()

    if current.strip():
        chunks.append(Chunk(index=len(chunks), text=current.strip()))

    limit = settings.ai_max_chunks
    if len(chunks) > limit:
        logger.info("Document produced %d chunks; using the first %d.", len(chunks), limit)
        chunks = chunks[:limit]
    return chunks
def extract_keywords(
    text: str,
    settings: Settings | None = None,
    limit: int | None = None,
) -> list[str]:
    """Frequency-ranked key terms, with stopwords and filler removed.

    Deliberately simple and dependency-free: this complements the abstractive
    summary with concrete terms a student can search on.
    """
    settings = settings or get_settings()
    limit = limit or settings.ai_max_keywords

    counts: Counter[str] = Counter()
    for match in _WORD.finditer(text.lower()):
        word = match.group(0).strip("'-")
        if len(word) < 3 or word in STOPWORDS or word in _GENERIC:
            continue
        counts[word] += 1

    if not counts:
        return []

    # Boost words that appear in several distinct places in the document.
    ranked = sorted(
        counts.items(),
        key=lambda item: (item[1] * (1 + 0.15 * text.lower().count(item[0]))),
        reverse=True,
    )
    return [word for word, _ in ranked[:limit]]


def first_sentences(text: str, count: int = 2, limit_chars: int = 320) -> str:
    """Leading sentences, used as a fallback summary when AI is unavailable."""
    text = " ".join(text.split())
    if not text:
        return ""
    parts = _SENTENCE_SPLIT.split(text)
    return " ".join(parts[:count]).strip()[:limit_chars]


def combine_summaries(parts: list[str], limit_chars: int = 1200) -> str:
    """Merge per-chunk summaries into one coherent block.

    Repeats are dropped by normalised-prefix comparison so overlapping chunks
    do not produce duplicated sentences.
    """
    merged: list[str] = []
    seen: set[str] = set()

    for part in parts:
        cleaned = " ".join(part.split()).strip()
        if not cleaned:
            continue
        normalised = cleaned.lower().rstrip(". ")
        if normalised in seen:
            continue
        seen.add(normalised)
        merged.append(cleaned)

    summary = " ".join(merged)
    if len(summary) > limit_chars:
        cut = summary[:limit_chars].rsplit(" ", 1)[0]
        summary = f"{cut}..."
    return summary

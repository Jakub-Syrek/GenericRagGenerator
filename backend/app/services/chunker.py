"""Split long text into overlapping character windows suitable for embedding."""
from __future__ import annotations

import re


class TextChunker:
    """Sentence-aware sliding-window chunker."""

    _SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")

    def __init__(self, chunk_size: int, overlap: int) -> None:
        """Configure target chunk size and overlap in characters.

        @param chunk_size Approximate maximum chunk length (characters).
        @param overlap    Number of trailing characters carried into next chunk.
        @raises ValueError When parameters are inconsistent.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be in [0, chunk_size)")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def split(self, text: str) -> list[str]:
        """Split text into chunks at sentence boundaries when possible.

        @param text Source text.
        @returns Non-empty list of chunks; empty list when input is blank.
        """
        normalized = text.strip()
        if not normalized:
            return []

        sentences = self._SENTENCE_BOUNDARY.split(normalized)
        chunks: list[str] = []
        buffer = ""
        for sentence in sentences:
            if not sentence:
                continue
            candidate = f"{buffer} {sentence}".strip() if buffer else sentence
            if len(candidate) <= self._chunk_size:
                buffer = candidate
                continue
            if buffer:
                chunks.append(buffer)
                buffer = self._carry_over(buffer) + sentence
            else:
                chunks.extend(self._hard_split(sentence))
                buffer = ""
        if buffer:
            chunks.append(buffer)
        return chunks

    def _carry_over(self, previous: str) -> str:
        """Return the trailing overlap fragment of the previous chunk.

        @param previous Previously emitted chunk.
        @returns Trailing slice of length up to `overlap`, padded with a space.
        """
        if self._overlap == 0:
            return ""
        tail = previous[-self._overlap:]
        return f"{tail} "

    def _hard_split(self, sentence: str) -> list[str]:
        """Slice a sentence longer than chunk_size into fixed windows.

        @param sentence Sentence that exceeds the configured chunk size.
        @returns List of windowed slices with configured overlap.
        """
        step = self._chunk_size - self._overlap
        return [sentence[i : i + self._chunk_size] for i in range(0, len(sentence), step)]

"""Sentence parsing utilities for the Mini Parser fixture."""

from __future__ import annotations


def parse_sentence(text: str) -> list[str]:
    """Split a sentence into whitespace-separated tokens after stripping punctuation.

    @param text Raw sentence.
    @returns Ordered list of alphanumeric tokens.
    """
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return [token for token in cleaned.split() if token]

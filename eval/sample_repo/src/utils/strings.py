"""String helpers used by the Mini Parser fixture."""

from __future__ import annotations


def slugify(value: str) -> str:
    """Lowercase the input and replace runs of whitespace with hyphens.

    @param value Raw string.
    @returns URL-friendly slug.
    """
    return "-".join(value.lower().split())

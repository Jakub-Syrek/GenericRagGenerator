"""Command-line entry point for the Mini Parser fixture."""

from __future__ import annotations

import argparse

from .parser import parse_sentence
from .utils.strings import slugify


def main() -> int:
    """Parse argv and print the slugified sentence to stdout.

    @returns Process exit code (always 0 on success).
    """
    parser = argparse.ArgumentParser(description="Sentence to URL slug")
    parser.add_argument("text", help="Sentence to slugify")
    args = parser.parse_args()
    tokens = parse_sentence(args.text)
    slugs = [slugify(token) for token in tokens]
    print("-".join(slugs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

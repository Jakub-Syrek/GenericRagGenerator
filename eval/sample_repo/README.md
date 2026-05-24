# Mini Parser

A tiny command-line tool that turns a sentence into a URL-friendly slug.
It exists as a small example project paired with its own documentation
for end-to-end testing.

## Running

```
python -m mini_parser.cli "Hello World"
```

The CLI passes the input string to `parse_sentence` to obtain a list of
tokens, then runs each token through the `slugify` helper before joining
the results with hyphens. The default output for `Hello World` is
`hello-world`.

## Layout

- `src/cli.py` — argument parsing entry point.
- `src/parser.py` — sentence tokeniser (`parse_sentence`).
- `src/utils/strings.py` — `slugify` helper used by the CLI.
- `docs/architecture.html` — high-level component description.

"""End-to-end RAG quality eval.

Fetches a small public corpus from Wikipedia, ingests it via the live API,
runs canned questions through `/api/chat`, and scores each answer by checking
whether any of the expected substrings appears in it. Results are written as
JSON + Markdown under `eval/results/`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from .corpus import CORPUS, EvalDocument, EvalQuestion

DEFAULT_BASE = "http://127.0.0.1:8765"
CORPUS_DIR = Path(__file__).parent / "corpus"
RESULTS_DIR = Path(__file__).parent / "results"


@dataclass(frozen=True)
class AnswerScore:
    """Score and trace for a single question."""

    document: str
    question: str
    answer: str
    sources: list[str]
    matched: list[str]
    expected_any: list[str]
    passed: bool
    latency_seconds: float


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    @returns Parsed argparse namespace.
    """
    parser = argparse.ArgumentParser(description="Run a RAG quality eval against the live API.")
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="Base URL of the running API.")
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use already-downloaded corpus files instead of fetching them again.",
    )
    return parser.parse_args()


def fetch_corpus(skip_download: bool) -> dict[str, Path]:
    """Download each corpus document and return a `filename -> local path` map.

    @param skip_download Reuse on-disk copies when True.
    @returns Mapping from corpus filename to the local file path.
    """
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for entry in CORPUS:
        path = CORPUS_DIR / entry.filename
        if skip_download and path.exists():
            paths[entry.filename] = path
            continue
        text = _fetch_wikipedia_summary(entry.url)
        path.write_text(text, encoding="utf-8")
        paths[entry.filename] = path
        print(f"[corpus] saved {entry.filename} ({len(text)} chars)")
    return paths


def _fetch_wikipedia_summary(url: str) -> str:
    """Fetch a Wikipedia REST `summary` extract.

    @param url Full REST API URL.
    @returns Plain-text article extract.
    @raises requests.HTTPError On non-2xx responses.
    """
    response = requests.get(
        url,
        headers={
            "User-Agent": "GenericRagGenerator-eval/1.0 (https://github.com/Jakub-Syrek/GenericRagGenerator)"
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    extract = payload.get("extract") or ""
    if not extract:
        raise RuntimeError(f"Empty extract for {url}")
    return f"{payload.get('title', '')}\n\n{extract}"


def reset_index(base_url: str) -> None:
    """Delete every previously indexed document via the API.

    @param base_url Base URL of the running API.
    """
    existing = requests.get(f"{base_url}/api/documents", timeout=30).json()
    for document in existing:
        requests.delete(f"{base_url}/api/documents/{document['id']}", timeout=30)
    print(f"[reset] cleared {len(existing)} pre-existing documents")


def ingest(base_url: str, paths: dict[str, Path]) -> dict[str, str]:
    """Upload every corpus document and return a `filename -> document_id` map.

    @param base_url Base URL of the running API.
    @param paths    Filename to local-path mapping.
    @returns Mapping from filename to assigned document id.
    """
    document_ids: dict[str, str] = {}
    for filename, path in paths.items():
        with path.open("rb") as handle:
            response = requests.post(
                f"{base_url}/api/documents",
                files={"file": (filename, handle, "text/plain")},
                timeout=300,
            )
            response.raise_for_status()
        body = response.json()
        document_ids[filename] = body["document"]["id"]
        print(f"[ingest] {filename} -> id={body['document']['id']} chunks={body['document']['chunks']}")
    return document_ids


def ask(base_url: str, question: str) -> tuple[str, list[str], float]:
    """Send a question to `/api/chat` and consume the NDJSON stream.

    @param base_url Base URL of the running API.
    @param question Question text.
    @returns Tuple of (full answer, source filenames, latency in seconds).
    """
    start = time.perf_counter()
    payload = {"messages": [{"role": "user", "content": question}]}
    with requests.post(f"{base_url}/api/chat", json=payload, stream=True, timeout=300) as response:
        response.raise_for_status()
        answer_parts: list[str] = []
        sources: list[str] = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            event = json.loads(line)
            if event["type"] == "delta":
                answer_parts.append(event["content"])
            elif event["type"] == "sources":
                sources = [item["filename"] for item in event.get("sources", [])]
            elif event["type"] == "error":
                raise RuntimeError(f"Chat error: {event.get('message')}")
    return "".join(answer_parts), sources, time.perf_counter() - start


def score(
    document: EvalDocument, question: EvalQuestion, answer: str, sources: list[str], latency: float
) -> AnswerScore:
    """Match expected substrings against the answer (case-insensitive).

    @param document Source document.
    @param question Canned question.
    @param answer   Model output.
    @param sources  Filenames cited in the streamed response.
    @param latency  Wall-clock seconds for the chat call.
    @returns Hydrated `AnswerScore`.
    """
    lowered = answer.lower()
    matched = [needle for needle in question.expected_any if needle.lower() in lowered]
    return AnswerScore(
        document=document.filename,
        question=question.prompt,
        answer=answer.strip(),
        sources=sources,
        matched=matched,
        expected_any=list(question.expected_any),
        passed=bool(matched),
        latency_seconds=round(latency, 2),
    )


def run(base_url: str, skip_download: bool) -> list[AnswerScore]:
    """Execute the full eval and return per-question scores.

    @param base_url      Base URL of the running API.
    @param skip_download Reuse on-disk corpus copies when True.
    @returns Ordered list of `AnswerScore` results.
    """
    paths = fetch_corpus(skip_download)
    reset_index(base_url)
    ingest(base_url, paths)
    results: list[AnswerScore] = []
    for document in CORPUS:
        for question in document.questions:
            print(f"[ask] {document.filename}: {question.prompt}")
            answer, sources, latency = ask(base_url, question.prompt)
            outcome = score(document, question, answer, sources, latency)
            mark = "PASS" if outcome.passed else "FAIL"
            print(f"  -> {mark} ({latency:.1f}s) sources={sources} matched={outcome.matched}")
            results.append(outcome)
    return results


def write_report(results: list[AnswerScore]) -> Path:
    """Persist the eval results as JSON and a human-readable Markdown summary.

    @param results Score list produced by `run()`.
    @returns Path of the Markdown report.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    json_path = RESULTS_DIR / f"eval-{stamp}.json"
    md_path = RESULTS_DIR / f"eval-{stamp}.md"

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "average_latency_seconds": round(sum(r.latency_seconds for r in results) / max(1, len(results)), 2),
    }
    json_path.write_text(
        json.dumps(
            {"summary": summary, "results": [asdict(r) for r in results]}, indent=2, ensure_ascii=False
        ),
        encoding="utf-8",
    )

    lines = [
        f"# RAG eval - {stamp}",
        "",
        f"- Total questions: **{summary['total']}**",
        f"- Passed: **{summary['passed']}**",
        f"- Failed: **{summary['failed']}**",
        f"- Average latency: **{summary['average_latency_seconds']}s**",
        "",
        "## Per-question results",
        "",
    ]
    for result in results:
        verdict = "PASS" if result.passed else "FAIL"
        lines.extend(
            [
                f"### {verdict} - {result.document}",
                f"- **Q:** {result.question}",
                f"- **A:** {result.answer}",
                f"- Sources: {', '.join(result.sources) or '(none)'}",
                f"- Matched: {', '.join(result.matched) or '(none)'} / expected any of: {', '.join(result.expected_any)}",
                f"- Latency: {result.latency_seconds}s",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> int:
    """Entry point for `python -m eval.run_eval`.

    @returns Process exit code (0 on success, 1 when any question failed).
    """
    args = parse_args()
    results = run(args.base_url, args.skip_download)
    report = write_report(results)
    passed = sum(1 for r in results if r.passed)
    print(f"\nReport: {report}")
    print(f"Score: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

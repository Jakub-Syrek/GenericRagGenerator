"""End-to-end RAG quality eval.

Fetches a small public corpus from Wikipedia, ingests it via the live API,
runs canned questions through `/api/chat`, and scores each answer on three
dimensions: substring match, top-1 retrieval precision, and (for out-of-
corpus probes) refusal. Reports are written under `eval/results/`.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from .corpus import (
    CORPUS,
    REFUSAL_PHRASES,
    REPOSITORY_NAME,
    REPOSITORY_QUESTIONS,
    EvalQuestion,
)

DEFAULT_BASE = "http://127.0.0.1:8765"
CORPUS_DIR = Path(__file__).parent / "corpus"
RESULTS_DIR = Path(__file__).parent / "results"
SAMPLE_REPO_DIR = Path(__file__).parent / "sample_repo"


@dataclass(frozen=True)
class AnswerScore:
    """Score and trace for a single question."""

    document: str
    question: str
    answer: str
    sources: list[str]
    top_source: str | None
    expected_top_source: str | None
    top_source_correct: bool
    top_kind: str | None
    expected_kind: str | None
    kind_correct: bool
    expected_any: list[str]
    matched: list[str]
    answer_match: bool
    ooc: bool
    refused: bool
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
    """Download each corpus document (skipping placeholder entries).

    @param skip_download Reuse on-disk copies when True.
    @returns Mapping from corpus filename to the local file path.
    """
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for entry in CORPUS:
        if not entry.url:
            continue
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
            "User-Agent": (
                "GenericRagGenerator-eval/1.0 " "(https://github.com/Jakub-Syrek/GenericRagGenerator)"
            )
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
    """Delete every previously indexed document and repository via the API.

    @param base_url Base URL of the running API.
    """
    docs = requests.get(f"{base_url}/api/documents", timeout=30).json()
    for document in docs:
        requests.delete(f"{base_url}/api/documents/{document['id']}", timeout=30)
    repos = requests.get(f"{base_url}/api/repositories", timeout=30).json()
    for repo in repos:
        requests.delete(f"{base_url}/api/repositories/{repo['id']}", timeout=30)
    print(f"[reset] cleared {len(docs)} documents, {len(repos)} repositories")


def build_sample_repo_zip() -> bytes:
    """Bundle the on-disk `eval/sample_repo/` tree into a ZIP archive in memory.

    @returns Raw ZIP bytes.
    @raises FileNotFoundError When the sample-repo fixture is missing.
    """
    if not SAMPLE_REPO_DIR.exists():
        raise FileNotFoundError(f"Missing sample repo at {SAMPLE_REPO_DIR}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(SAMPLE_REPO_DIR.rglob("*")):
            if path.is_dir():
                continue
            rel = f"{REPOSITORY_NAME}/{path.relative_to(SAMPLE_REPO_DIR).as_posix()}"
            archive.writestr(rel, path.read_bytes())
    return buffer.getvalue()


def ingest_repository(base_url: str, archive_bytes: bytes) -> dict:
    """Upload the sample repository via `/api/repositories`.

    @param base_url      Base URL of the running API.
    @param archive_bytes Raw ZIP archive bytes.
    @returns The decoded JSON response.
    @raises requests.HTTPError When the upload fails.
    """
    response = requests.post(
        f"{base_url}/api/repositories",
        files={"file": (f"{REPOSITORY_NAME}.zip", archive_bytes, "application/zip")},
        timeout=300,
    )
    response.raise_for_status()
    body = response.json()
    repo = body["repository"]
    print(
        f"[repo] {repo['name']} -> id={repo['id']} files={repo['files_indexed']} "
        f"chunks={repo['total_chunks']} skipped={len(repo.get('skipped', []))}"
    )
    return body


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
        print(f"[ingest] {filename} -> id={body['document']['id']} " f"chunks={body['document']['chunks']}")
    return document_ids


def ask(base_url: str, question: str) -> tuple[str, list[dict], float]:
    """Send a question to `/api/chat` and consume the NDJSON stream.

    @param base_url Base URL of the running API.
    @param question Question text.
    @returns Tuple of (full answer, full source descriptors, latency seconds).
    """
    start = time.perf_counter()
    payload = {"messages": [{"role": "user", "content": question}]}
    with requests.post(f"{base_url}/api/chat", json=payload, stream=True, timeout=300) as response:
        response.raise_for_status()
        answer_parts: list[str] = []
        sources: list[dict] = []
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            event = json.loads(line)
            if event["type"] == "delta":
                answer_parts.append(event["content"])
            elif event["type"] == "sources":
                sources = list(event.get("sources", []))
            elif event["type"] == "error":
                raise RuntimeError(f"Chat error: {event.get('message')}")
    return "".join(answer_parts), sources, time.perf_counter() - start


def _is_refusal(answer: str) -> bool:
    """Detect whether `answer` reads as a refusal grounded in missing context.

    @param answer Lowercased or raw answer text.
    @returns True when any of the configured refusal phrases is present.
    """
    lowered = answer.lower()
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)


def score(
    document_label: str,
    question: EvalQuestion,
    answer: str,
    sources: list[dict],
    latency: float,
) -> AnswerScore:
    """Compute the per-question score.

    For in-corpus questions, `passed` requires substring match, top-1 path
    match and (when set) kind match. For out-of-corpus probes, `passed`
    requires a refusal.

    @param document_label Identifier shown in the report (filename / repo / ooc).
    @param question       Canned question.
    @param answer         Model output.
    @param sources        Source descriptors cited in the streamed response.
    @param latency        Wall-clock seconds for the chat call.
    @returns Hydrated `AnswerScore`.
    """
    lowered = answer.lower()
    matched = [needle for needle in question.expected_any if needle.lower() in lowered]
    top = sources[0] if sources else None
    top_source = top.get("filename") if top else None
    top_kind = top.get("kind") if top else None
    top_source_correct = (
        question.expected_top_source is not None and top_source == question.expected_top_source
    )
    kind_correct = question.expected_kind is None or top_kind == question.expected_kind
    refused = _is_refusal(answer)
    answer_match = bool(matched)
    passed = refused if question.ooc else (answer_match and top_source_correct and kind_correct)

    return AnswerScore(
        document=document_label,
        question=question.prompt,
        answer=answer.strip(),
        sources=[source.get("filename", "") for source in sources],
        top_source=top_source,
        expected_top_source=question.expected_top_source,
        top_source_correct=top_source_correct,
        top_kind=top_kind,
        expected_kind=question.expected_kind,
        kind_correct=kind_correct,
        expected_any=list(question.expected_any),
        matched=matched,
        answer_match=answer_match,
        ooc=question.ooc,
        refused=refused,
        passed=passed,
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
    ingest_repository(base_url, build_sample_repo_zip())
    results: list[AnswerScore] = []
    for document in CORPUS:
        for question in document.questions:
            results.append(_run_question(base_url, document.filename, question))
    for question in REPOSITORY_QUESTIONS:
        results.append(_run_question(base_url, REPOSITORY_NAME, question))
    return results


def _run_question(base_url: str, label: str, question: EvalQuestion) -> AnswerScore:
    """Issue one question and print a one-line trace.

    @param base_url Base URL of the running API.
    @param label    Document / repo / ooc label shown in the trace.
    @param question Canned question.
    @returns Hydrated `AnswerScore`.
    """
    print(f"[ask] {('ooc' if question.ooc else label)}: {question.prompt}")
    answer, sources, latency = ask(base_url, question.prompt)
    outcome = score(label, question, answer, sources, latency)
    mark = "PASS" if outcome.passed else "FAIL"
    extras: list[str] = []
    if question.ooc:
        extras.append(f"refused={outcome.refused}")
    else:
        extras.append(f"top={outcome.top_source}/{outcome.expected_top_source}")
        extras.append(f"kind={outcome.top_kind}/{outcome.expected_kind}")
        extras.append(f"matched={outcome.matched}")
    print(f"  -> {mark} ({latency:.1f}s) " + " ".join(extras))
    return outcome


def _summarise(results: list[AnswerScore]) -> dict[str, float | int]:
    """Aggregate per-question scores into headline metrics.

    @param results Score list produced by `run()`.
    @returns Dict of summary metrics.
    """
    in_corpus = [r for r in results if not r.ooc]
    ooc = [r for r in results if r.ooc]
    kind_questions = [r for r in in_corpus if r.expected_kind is not None]
    in_corpus_retrieval = (
        sum(1 for r in in_corpus if r.top_source_correct) / len(in_corpus) if in_corpus else 0.0
    )
    in_corpus_answer_match = (
        sum(1 for r in in_corpus if r.answer_match) / len(in_corpus) if in_corpus else 0.0
    )
    kind_precision = (
        sum(1 for r in kind_questions if r.kind_correct) / len(kind_questions) if kind_questions else 0.0
    )
    refusal_rate = sum(1 for r in ooc if r.refused) / len(ooc) if ooc else 0.0
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "in_corpus_count": len(in_corpus),
        "ooc_count": len(ooc),
        "retrieval_top1_precision": round(in_corpus_retrieval, 3),
        "answer_substring_match": round(in_corpus_answer_match, 3),
        "kind_precision": round(kind_precision, 3),
        "ooc_refusal_rate": round(refusal_rate, 3),
        "average_latency_seconds": round(sum(r.latency_seconds for r in results) / max(1, len(results)), 2),
    }


def write_report(results: list[AnswerScore]) -> Path:
    """Persist the eval results as JSON and a Markdown summary.

    @param results Score list produced by `run()`.
    @returns Path of the Markdown report.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    json_path = RESULTS_DIR / f"eval-{stamp}.json"
    md_path = RESULTS_DIR / f"eval-{stamp}.md"
    summary = _summarise(results)

    json_path.write_text(
        json.dumps(
            {"summary": summary, "results": [asdict(r) for r in results]},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lines = [
        f"# RAG eval - {stamp}",
        "",
        f"- Total questions: **{summary['total']}** "
        f"(in-corpus {summary['in_corpus_count']}, OOC {summary['ooc_count']})",
        f"- Passed (composite): **{summary['passed']}** / {summary['total']}",
        f"- Retrieval top-1 precision: **{summary['retrieval_top1_precision']}**",
        f"- Answer substring match: **{summary['answer_substring_match']}**",
        f"- Kind precision (code vs doc): **{summary['kind_precision']}**",
        f"- OOC refusal rate: **{summary['ooc_refusal_rate']}**",
        f"- Average latency: **{summary['average_latency_seconds']}s**",
        "",
        "## Per-question results",
        "",
    ]
    for result in results:
        verdict = "PASS" if result.passed else "FAIL"
        kind = "OOC" if result.ooc else result.document
        lines.append(f"### {verdict} - {kind}")
        lines.append(f"- **Q:** {result.question}")
        lines.append(f"- **A:** {result.answer}")
        lines.append(f"- Sources: {', '.join(result.sources) or '(none)'}")
        if result.ooc:
            lines.append(f"- Refused: {result.refused}")
        else:
            lines.append(
                f"- Top source: {result.top_source} "
                f"(expected {result.expected_top_source}) -> "
                f"{'OK' if result.top_source_correct else 'wrong'}"
            )
            if result.expected_kind is not None:
                lines.append(
                    f"- Top kind: {result.top_kind} (expected {result.expected_kind}) -> "
                    f"{'OK' if result.kind_correct else 'wrong'}"
                )
            lines.append(
                f"- Matched: {', '.join(result.matched) or '(none)'} "
                f"/ expected any of: {', '.join(result.expected_any)}"
            )
        lines.append(f"- Latency: {result.latency_seconds}s")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main() -> int:
    """Entry point for `python -m eval.run_eval`.

    @returns Process exit code (0 on perfect score, 1 otherwise).
    """
    args = parse_args()
    results = run(args.base_url, args.skip_download)
    report = write_report(results)
    summary = _summarise(results)
    print(f"\nReport: {report}")
    print(
        f"Composite: {summary['passed']}/{summary['total']} | "
        f"retrieval_top1={summary['retrieval_top1_precision']} | "
        f"answer_match={summary['answer_substring_match']} | "
        f"kind={summary['kind_precision']} | "
        f"ooc_refusal={summary['ooc_refusal_rate']}"
    )
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    sys.exit(main())

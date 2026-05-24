"""Quick end-to-end smoke test: upload a doc, ask a question, stream answer."""
import json
import sys
import tempfile
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8765"

SAMPLE = (
    "GenericRagGenerator is a local Retrieval-Augmented Generation application built by Jakub Syrek.\n"
    "It uses the Ollama runtime to serve open-source language models on the user's own machine.\n"
    "The default chat model is llama3.1:8b and the default embedding model is nomic-embed-text.\n"
    "ChromaDB is used as an embedded vector database stored under ./data/chroma.\n"
    "The maximum upload size is 25 megabytes.\n"
)


def main() -> int:
    """Run the smoke test and print a transcript.

    @returns 0 on success, non-zero otherwise.
    """
    tmp = Path(tempfile.gettempdir()) / "rag_smoke.txt"
    tmp.write_text(SAMPLE, encoding="utf-8")
    with tmp.open("rb") as handle:
        upload = requests.post(f"{BASE}/api/documents", files={"file": ("rag_smoke.txt", handle, "text/plain")}, timeout=120)
    print("UPLOAD:", upload.status_code, upload.json())

    docs = requests.get(f"{BASE}/api/documents", timeout=30).json()
    print("LIST:", docs)

    payload = {"messages": [{"role": "user", "content": "Which embedding model does the project use by default?"}]}
    with requests.post(f"{BASE}/api/chat", json=payload, stream=True, timeout=120) as response:
        print("CHAT status:", response.status_code)
        full = ""
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            event = json.loads(line)
            if event["type"] == "delta":
                full += event["content"]
            elif event["type"] == "sources":
                print("SOURCES:", [s["filename"] for s in event["sources"]])
            elif event["type"] == "error":
                print("ERROR:", event["message"])
        print("ANSWER:", full)

    if docs:
        requests.delete(f"{BASE}/api/documents/{docs[0]['id']}", timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())

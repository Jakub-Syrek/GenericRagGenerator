# RAG eval - 20260524-122508

- Total questions: **17** (in-corpus 15, OOC 2)
- Passed (composite): **17** / 17
- Retrieval top-1 precision: **1.0**
- Answer substring match: **1.0**
- Kind precision (code vs doc): **1.0**
- OOC refusal rate: **1.0**
- Average latency: **1.27s**

## Per-question results

### PASS - rag.txt
- **Q:** In the article about retrieval-augmented generation, what is the full name behind the acronym RAG?
- **A:** Retrieval-augmented generation (Source: rag.txt)
- Sources: rag.txt, docs/architecture.html, src/cli.py, src/utils/strings.py
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: retrieval-augmented generation / expected any of: retrieval-augmented generation, retrieval augmented generation
- Latency: 13.31s

### PASS - rag.txt
- **Q:** What kind of model does RAG combine retrieval with?
- **A:** According to the document excerpt (rag.txt), RAG combines retrieval with large language models (LLMs). (Source: rag.txt)
- Sources: rag.txt, src/utils/strings.py, docs/architecture.html, src/parser.py
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: language model, llm / expected any of: language model, generative, llm
- Latency: 0.71s

### PASS - rag.txt
- **Q:** Why would someone use RAG instead of a plain language model?
- **A:** According to the document "rag.txt", the main reason for using Retrieval-augmented generation (RAG) is that it enables large language models (LLMs) to incorporate new information from external data sources, which may not be available in their pre-existing training data. This allows LLMs to use domain-specific and/or updated information, such as internal company data or authoritative sources, making them more accurate and informative.
- Sources: rag.txt, docs/architecture.html, src/parser.py, src/cli.py
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: updated, external, domain-specific, training data / expected any of: up-to-date, current, updated, private, external, domain-specific, training data, factual, hallucin
- Latency: 0.94s

### PASS - vector_database.txt
- **Q:** What kind of data does a vector database store?
- **A:** A vector database stores embeddings of data in vector space. (vector_database.txt)
- Sources: vector_database.txt, rag.txt, word_embedding.txt, src/utils/strings.py
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: vector, embedding / expected any of: vector, embedding, high-dimensional, high dimensional
- Latency: 0.34s

### PASS - vector_database.txt
- **Q:** What kind of search do vector databases enable?
- **A:** Vector databases enable similarity search, semantic search, multi-modal search (Source: vector_database.txt).
- Sources: vector_database.txt, rag.txt, docs/architecture.html, README.md
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: similarity, semantic / expected any of: similarity, nearest neighbor, semantic
- Latency: 0.32s

### PASS - vector_database.txt
- **Q:** Name one common application of vector databases.
- **A:** One common application of vector databases is similarity search (Source: vector_database.txt).
- Sources: vector_database.txt, rag.txt, docs/architecture.html, README.md
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: search / expected any of: recommendation, search, retrieval, rag, image, machine learning
- Latency: 0.26s

### PASS - word_embedding.txt
- **Q:** In word embeddings, what are words mapped to?
- **A:** According to the word_embedding.txt document (word_embedding.txt), in word embeddings, words are mapped to "vectors of real numbers."
- Sources: word_embedding.txt, docs/architecture.html, rag.txt, README.md
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: vector, real number, embedding / expected any of: vector, real number, real-valued, real value, embedding, numeric
- Latency: 0.46s

### PASS - word_embedding.txt
- **Q:** What property of words is captured by their embedding vectors?
- **A:** According to the document "word_embedding.txt", word embeddings capture the meaning of a word, such that words that are closer in the vector space are expected to be similar in meaning. (Source: word_embedding.txt)
- Sources: word_embedding.txt, vector_database.txt, rag.txt, src/parser.py
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: meaning, similar / expected any of: meaning, semantic, similar, context, syntactic, distribution
- Latency: 0.54s

### PASS - photosynthesis.txt
- **Q:** What gas does photosynthesis release as a byproduct?
- **A:** Oxygen (Source: photosynthesis.txt)
- Sources: photosynthesis.txt, docs/architecture.html, src/cli.py, rag.txt
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: oxygen / expected any of: oxygen
- Latency: 0.31s

### PASS - photosynthesis.txt
- **Q:** What kind of energy do photosynthetic organisms convert during photosynthesis?
- **A:** According to the document "photosynthesis.txt", photopigment-bearing autotrophic organisms, such as most plants, algae and cyanobacteria, convert light energy (typically from sunlight) into the chemical energy necessary to fuel their metabolism. (photosynthesis.txt)
- Sources: photosynthesis.txt, docs/architecture.html, src/parser.py, src/utils/strings.py
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: light, sunlight, chemical / expected any of: light, sunlight, chemical
- Latency: 0.63s

### PASS - OOC
- **Q:** What are the typical symptoms of malaria in humans?
- **A:** The documents do not cover it.
- Sources: docs/architecture.html, README.md, src/cli.py, README.md
- Refused: True
- Latency: 0.26s

### PASS - OOC
- **Q:** Who won the FIFA World Cup in 2022?
- **A:** The documents do not cover it.
- Sources: README.md, src/parser.py, docs/architecture.html, src/cli.py
- Refused: True
- Latency: 0.25s

### PASS - mini_parser
- **Q:** What transformation does the slugify helper apply to its input string?
- **A:** The `slugify` helper applies two transformations to its input string:

1. Lowercase the input.
2. Replace runs of whitespace with hyphens.

(Source: src/utils/strings.py)
- Sources: src/utils/strings.py, src/cli.py, docs/architecture.html, README.md
- Top source: src/utils/strings.py (expected src/utils/strings.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: lowercase, lower, hyphen, whitespace / expected any of: lowercase, lower, hyphen, whitespace
- Latency: 0.57s

### PASS - mini_parser
- **Q:** What does parse_sentence do in the mini_parser project?
- **A:** According to the documentation (src/parser.py), the `parse_sentence` function splits a sentence into whitespace-separated tokens after stripping punctuation.

Source: (src/parser.py)

```python
def parse_sentence(text: str) -> list[str]:
    """Split a sentence into whitespace-separated tokens after stripping punctuation.

    @param text Raw sentence.
    @returns Ordered list of alphanumeric tokens.
    """
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return [token for token in cleaned.split() if token]
```
- Sources: src/parser.py, docs/architecture.html, README.md, src/cli.py
- Top source: src/parser.py (expected src/parser.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: token, whitespace, punctuation, split / expected any of: token, whitespace, punctuation, split
- Latency: 1.22s

### PASS - mini_parser
- **Q:** According to the README, how do you run the mini_parser project from the command line?
- **A:** To run the mini_parser project from the command line, use:

```
python -m mini_parser.cli "Hello World"
```

(Source: README.md)
- Sources: README.md, docs/architecture.html, src/cli.py, README.md
- Top source: README.md (expected README.md) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: python -m mini_parser.cli, mini_parser.cli / expected any of: python -m mini_parser.cli, mini_parser.cli
- Latency: 0.47s

### PASS - mini_parser
- **Q:** What three layers are described in the architecture document?
- **A:** The Mini Parser project is split into three layers, each living under src/:

1. cli - the entry point.
2. parser - splits sentences into tokens via the parse_sentence function.
3. utils.strings - hosts the slugify helper that lowercases its input and replaces whitespace with hyphens.

(Sourced from docs/architecture.html)
- Sources: docs/architecture.html, README.md, rag.txt, README.md
- Top source: docs/architecture.html (expected docs/architecture.html) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: cli, parser, utils / expected any of: cli, parser, utils
- Latency: 0.79s

### PASS - mini_parser
- **Q:** Which Python standard-library module does the mini_parser CLI import to parse arguments?
- **A:** argparse (Source: src/cli.py)
- Sources: src/cli.py, README.md, docs/architecture.html, src/parser.py
- Top source: src/cli.py (expected src/cli.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: argparse / expected any of: argparse
- Latency: 0.28s

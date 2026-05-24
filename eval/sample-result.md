# RAG eval - 20260524-134242

- Total questions: **24** (in-corpus 21, OOC 3)
- Passed (composite): **24** / 24
- Retrieval top-1 precision: **1.0**
- Answer substring match: **1.0**
- Kind precision (code vs doc): **1.0**
- OOC refusal rate: **1.0**
- Average latency: **0.54s**

## Per-question results

### PASS - rag.txt
- **Q:** In the article about retrieval-augmented generation, what is the full name behind the acronym RAG?
- **A:** Retrieval-augmented generation (RAG) is a technique that enables large language models (LLMs) to retrieve and incorporate new information from external data sources. With RAG, LLMs first refer to a specified set of documents, then respond to user queries. These documents supplement information from the LLM's pre-existing training data. This allows LLMs to use domain-specific and/or updated information that is not available in the training data. For example, this helps LLM-based chatbots access internal company data or generate responses based on authoritative sources.

(Rag.txt)
- Sources: rag.txt, docs/architecture.html, src/cli.py, src/utils/strings.py, src/parser.py, vector_database.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: retrieval-augmented generation / expected any of: retrieval-augmented generation, retrieval augmented generation
- Latency: 1.71s

### PASS - rag.txt
- **Q:** What kind of model does RAG combine retrieval with?
- **A:** The document doesn't specify the type of model that RAG combines retrieval with. However, it is mentioned in the context of large language models (LLMs) as a technique that enables them to retrieve and incorporate new information from external data sources.

(Retrieval-augmented generation (RAG))
- Sources: rag.txt, src/utils/strings.py, docs/architecture.html, src/parser.py, src/cli.py, vector_database.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: language model, llm / expected any of: language model, generative, llm
- Latency: 0.66s

### PASS - rag.txt
- **Q:** Why would someone use RAG instead of a plain language model?
- **A:** (Rag.txt) Retrieval-augmented generation (RAG) allows large language models to retrieve and incorporate new information from external data sources, supplementing their pre-existing training data. This enables them to access domain-specific and/or updated information that is not available in the training data. For example, this helps LLM-based chatbots access internal company data or generate responses based on authoritative sources.
- Sources: rag.txt, docs/architecture.html, src/parser.py, src/cli.py, src/utils/strings.py, README.md
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: updated, external, domain-specific, training data / expected any of: up-to-date, current, updated, private, external, domain-specific, training data, factual, hallucin
- Latency: 0.77s

### PASS - vector_database.txt
- **Q:** What kind of data does a vector database store?
- **A:** Vector databases typically store and retrieve embeddings of data in vector space (vector_database.txt).
- Sources: vector_database.txt, rag.txt, word_embedding.txt, src/utils/strings.py, docs/architecture.html, README.md
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: vector, embedding / expected any of: vector, embedding, high-dimensional, high dimensional
- Latency: 0.34s

### PASS - vector_database.txt
- **Q:** What kind of search do vector databases enable?
- **A:** Vector databases typically implement approximate nearest neighbor algorithms so users can search for records semantically similar to a given input, unlike traditional databases which primarily look up records by exact match. (vector_database.txt)
- Sources: vector_database.txt, rag.txt, docs/architecture.html, README.md, src/utils/strings.py, word_embedding.txt
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: nearest neighbor, semantic / expected any of: similarity, nearest neighbor, semantic
- Latency: 0.46s

### PASS - vector_database.txt
- **Q:** Name one common application of vector databases.
- **A:** Similarity search (Source: vector_database.txt)
- Sources: vector_database.txt, rag.txt, docs/architecture.html, README.md, word_embedding.txt, README.md
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: search / expected any of: recommendation, search, retrieval, rag, image, machine learning, object detection, multi-modal, semantic
- Latency: 0.22s

### PASS - word_embedding.txt
- **Q:** In word embeddings, what are words mapped to?
- **A:** According to the document (word_embedding.txt), in word embeddings, words are mapped to vectors of real numbers.
- Sources: word_embedding.txt, docs/architecture.html, rag.txt, README.md, README.md, src/parser.py
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: vector, real number, embedding / expected any of: vector, real number, real-valued, real value, embedding, numeric
- Latency: 0.35s

### PASS - word_embedding.txt
- **Q:** What property of words is captured by their embedding vectors?
- **A:** According to the document excerpt "word_embedding.txt", word embeddings capture the meaning of a word in such a way that the words that are closer in the vector space are expected to be similar in meaning. (Source: word_embedding.txt)
- Sources: word_embedding.txt, vector_database.txt, rag.txt, src/parser.py, docs/architecture.html, src/utils/strings.py
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: meaning, similar / expected any of: meaning, semantic, similar, context, syntactic, distribution
- Latency: 0.53s

### PASS - photosynthesis.txt
- **Q:** What gas does photosynthesis release as a byproduct?
- **A:** According to the document excerpt "photosynthesis.txt", oxygen is released as a byproduct of water splitting during oxygenic photosynthesis. (photosynthesis.txt)
- Sources: photosynthesis.txt, docs/architecture.html, src/cli.py, rag.txt, src/utils/strings.py, src/parser.py
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: oxygen / expected any of: oxygen
- Latency: 0.46s

### PASS - photosynthesis.txt
- **Q:** What kind of energy do photosynthetic organisms convert during photosynthesis?
- **A:** Light energy (typically from sunlight) is converted into chemical energy during photosynthesis. (Source: photosynthesis.txt)
- Sources: photosynthesis.txt, docs/architecture.html, src/parser.py, src/utils/strings.py, README.md, rag.txt
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: light, sunlight, chemical / expected any of: light, sunlight, chemical
- Latency: 0.35s

### PASS - OOC
- **Q:** What are the typical symptoms of malaria in humans?
- **A:** The documents do not cover this topic.
- Sources: docs/architecture.html, README.md, src/cli.py, README.md, photosynthesis.txt, README.md
- Refused: True
- Latency: 0.28s

### PASS - OOC
- **Q:** Who won the FIFA World Cup in 2022?
- **A:** The documents do not cover this topic.
- Sources: README.md, src/parser.py, docs/architecture.html, src/cli.py, rag.txt, src/utils/strings.py
- Refused: True
- Latency: 0.28s

### PASS - mini_parser
- **Q:** What transformation does the slugify helper apply to its input string?
- **A:** The `slugify` helper (found in `src/utils/strings.py`) applies two transformations to its input string:

1. Lowercase conversion (it converts the input string to lowercase).
2. Run replacement (it replaces runs of whitespace with hyphens).

The resulting transformation is applied by joining the split and lowercased string with hyphens, as shown in the implementation: `return "-".join(value.lower().split())`. (src/utils/strings.py)
- Sources: src/utils/strings.py, src/cli.py, docs/architecture.html, README.md, rag.txt, README.md
- Top source: src/utils/strings.py (expected src/utils/strings.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: lowercase, lower, hyphen, whitespace / expected any of: lowercase, lower, hyphen, whitespace
- Latency: 0.91s

### PASS - mini_parser
- **Q:** What does parse_sentence do in the mini_parser project?
- **A:** The `parse_sentence` function (found in `src/parser.py`) splits a raw sentence into whitespace-separated tokens after stripping punctuation. It returns an ordered list of alphanumeric tokens. (1)
- Sources: src/parser.py, docs/architecture.html, README.md, src/cli.py, README.md, README.md
- Top source: src/parser.py (expected src/parser.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: token, whitespace, punctuation, split / expected any of: token, whitespace, punctuation, split
- Latency: 0.54s

### PASS - mini_parser
- **Q:** According to the README, how do you run the mini_parser project from the command line?
- **A:** You can run the Mini Parser project from the command line by running:

```
python -m mini_parser.cli "Hello World"
```
- Sources: README.md, docs/architecture.html, src/cli.py, README.md, README.md, src/parser.py
- Top source: README.md (expected README.md) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: python -m mini_parser.cli, mini_parser.cli / expected any of: python -m mini_parser.cli, mini_parser.cli
- Latency: 0.41s

### PASS - mini_parser
- **Q:** What three layers are described in the architecture document?
- **A:** The Mini Parser project is split into three layers, each living under `src/`:

1. cli — the entry point. Parses command-line arguments and orchestrates the pipeline.
2. parser — splits sentences into tokens via the parse_sentence function. Strips punctuation before tokenising.
3. utils.strings — hosts the slugify helper that lowercases its input and replaces whitespace with hyphens.

(Source: docs/architecture.html)
- Sources: docs/architecture.html, README.md, rag.txt, README.md, README.md, src/parser.py
- Top source: docs/architecture.html (expected docs/architecture.html) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: cli, parser, utils / expected any of: cli, parser, utils
- Latency: 0.83s

### PASS - mini_parser
- **Q:** Which Python standard-library module does the mini_parser CLI import to parse arguments?
- **A:** argparse (src/cli.py)
- Sources: src/cli.py, README.md, docs/architecture.html, src/parser.py, README.md, src/utils/strings.py
- Top source: src/cli.py (expected src/cli.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: argparse / expected any of: argparse
- Latency: 0.26s

### PASS - mini_parser
- **Q:** Which two `str` methods does parse_sentence call on each character to decide whether to keep it or replace it with whitespace?
- **A:** The function `parse_sentence` uses the following methods:

1. `isalnum()` - to check if a character is alphanumeric (either a letter or a number)
2. `isspace()` - to check if a character is a whitespace

These methods are called on each character (`ch`) in the input string to decide whether to keep it (`if ch.isalnum() or ch.isspace():`) or replace it with whitespace (`else " "`). (src/parser.py)
- Sources: src/parser.py, src/cli.py, docs/architecture.html, src/utils/strings.py, README.md, README.md
- Top source: src/parser.py (expected src/parser.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: isalnum, isspace / expected any of: isalnum, isspace
- Latency: 0.89s

### PASS - mini_parser
- **Q:** Which attribute of the parsed argparse namespace does cli.py pass to parse_sentence?
- **A:** The parsed `argparse` namespace's "text" attribute is passed to `parse_sentence`. (src/cli.py)
- Sources: src/cli.py, src/parser.py, docs/architecture.html, README.md, README.md, src/utils/strings.py
- Top source: src/cli.py (expected src/cli.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: "text" / expected any of: args.text, text attribute, "text", 'text'
- Latency: 0.39s

### PASS - mini_parser
- **Q:** How does slugify split its input into pieces before joining them with hyphens?
- **A:** According to the source file `src/utils/strings.py` (1), the function `slugify(value: str) -> str:` splits its input into pieces by calling the `split()` method on the lowercased input string, and then joins these pieces with hyphens using the `join()` method.
- Sources: src/utils/strings.py, docs/architecture.html, src/cli.py, README.md, src/parser.py, README.md
- Top source: src/utils/strings.py (expected src/utils/strings.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: split / expected any of: split, whitespace
- Latency: 0.67s

### PASS - mini_parser
- **Q:** According to the README, what does the mini_parser project exist as?
- **A:** A tiny command-line tool that turns a sentence into a URL-friendly slug. It exists as a small example project paired with its own documentation for end-to-end testing. (README.md)
- Sources: README.md, docs/architecture.html, src/cli.py, README.md, README.md, src/parser.py
- Top source: README.md (expected README.md) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: example project, end-to-end testing, paired with, documentation / expected any of: example project, end-to-end testing, paired with, documentation
- Latency: 0.48s

### PASS - mini_parser
- **Q:** According to the architecture document, in which direction does data flow through the three layers?
- **A:** Data flows linearly from the CLI (Command-Line Interface) layer through the parser layer to the utils layer. (docs/architecture.html)
- Sources: docs/architecture.html, README.md, README.md, rag.txt, README.md, src/cli.py
- Top source: docs/architecture.html (expected docs/architecture.html) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: linearly, from the cli / expected any of: linearly, from the cli, no cycles, no side effects
- Latency: 0.42s

### PASS - mini_parser
- **Q:** From which module does the mini_parser CLI import the slugify helper?
- **A:** (src/utils/strings.py) (The source is src/utils/strings.py where the function `slugify` is located.)
- Sources: src/cli.py, src/utils/strings.py, docs/architecture.html, README.md, README.md, README.md
- Top source: src/cli.py (expected src/cli.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: utils/strings / expected any of: utils.strings, utils/strings, .utils.strings
- Latency: 0.37s

### PASS - OOC
- **Q:** Does the mini_parser project document any retry behaviour on network failures?
- **A:** The documents do not cover it.
- Sources: docs/architecture.html, README.md, src/cli.py, src/parser.py, README.md, src/utils/strings.py
- Refused: True
- Latency: 0.26s

# RAG eval - 20260524-140934

- Total questions: **24** (in-corpus 21, OOC 3)
- Passed (composite): **24** / 24
- Retrieval top-1 precision: **1.0**
- Answer substring match: **1.0**
- Kind precision (code vs doc): **1.0**
- OOC refusal rate: **1.0**
- Average latency: **0.6s**

## Per-question results

### PASS - rag.txt
- **Q:** In the article about retrieval-augmented generation, what is the full name behind the acronym RAG?
- **A:** Retrieval-augmented generation (RAG) is not explicitly mentioned with its expansion in the provided excerpts. However, based on the context of "retrieval-augmented generation" it can be inferred that RAG stands for Retrieval-Augmented Generation.
- Sources: rag.txt, docs/architecture.html, src/cli.py, src/utils/strings.py, src/parser.py, vector_database.txt, README.md, word_embedding.txt, README.md, README.md, photosynthesis.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: retrieval-augmented generation / expected any of: retrieval-augmented generation, retrieval augmented generation
- Latency: 1.31s

### PASS - rag.txt
- **Q:** What kind of model does RAG combine retrieval with?
- **A:** The document excerpts do not explicitly state what kind of model RAG combines retrieval with. However, based on the context, it is likely that Retrieval-augmented generation (RAG) is a technique used with Large Language Models (LLMs).

(Retrieval-augmented generation (RAG) is a technique that enables large language models (LLMs) to retrieve and incorporate new information from external data sources.)
- Sources: rag.txt, src/utils/strings.py, docs/architecture.html, src/parser.py, src/cli.py, vector_database.txt, README.md, README.md, README.md, word_embedding.txt, photosynthesis.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: language model, llm / expected any of: language model, generative, llm
- Latency: 0.91s

### PASS - rag.txt
- **Q:** Why would someone use RAG instead of a plain language model?
- **A:** According to the document excerpt "rag.txt", someone would use Retrieval-augmented generation (RAG) because it allows large language models (LLMs) to retrieve and incorporate new information from external data sources, which are not available in the LLM's pre-existing training data. This is particularly useful for domain-specific or updated information that can be accessed through authoritative sources.
- Sources: rag.txt, docs/architecture.html, src/parser.py, src/cli.py, src/utils/strings.py, README.md, README.md, README.md, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: updated, external, domain-specific, training data / expected any of: up-to-date, current, updated, private, external, domain-specific, training data, factual, hallucin
- Latency: 0.82s

### PASS - vector_database.txt
- **Q:** What kind of data does a vector database store?
- **A:** A vector database stores embeddings of data in vector space (vector_database.txt).
- Sources: vector_database.txt, rag.txt, word_embedding.txt, src/utils/strings.py, docs/architecture.html, README.md, README.md, src/parser.py, src/cli.py, README.md, photosynthesis.txt
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: vector, embedding / expected any of: vector, embedding, high-dimensional, high dimensional
- Latency: 0.39s

### PASS - vector_database.txt
- **Q:** What kind of search do vector databases enable?
- **A:** Vector databases typically implement approximate nearest neighbor algorithms so users can search for records semantically similar to a given input, unlike traditional databases which primarily look up records by exact match. (vector_database.txt)
- Sources: vector_database.txt, rag.txt, docs/architecture.html, README.md, src/utils/strings.py, word_embedding.txt, README.md, README.md, src/cli.py, src/parser.py, photosynthesis.txt
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: nearest neighbor, semantic / expected any of: similarity, nearest neighbor, semantic
- Latency: 0.55s

### PASS - vector_database.txt
- **Q:** Name one common application of vector databases.
- **A:** One common application of vector databases is similarity search (Source: vector_database.txt).
- Sources: vector_database.txt, rag.txt, docs/architecture.html, README.md, word_embedding.txt, README.md, src/utils/strings.py, README.md, src/cli.py, src/parser.py, photosynthesis.txt
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: search / expected any of: recommendation, search, retrieval, rag, image, machine learning, object detection, multi-modal, semantic
- Latency: 0.35s

### PASS - word_embedding.txt
- **Q:** In word embeddings, what are words mapped to?
- **A:** According to the document "word_embedding.txt", words or phrases from the vocabulary are mapped to vectors of real numbers (Source: word_embedding.txt).
- Sources: word_embedding.txt, docs/architecture.html, rag.txt, README.md, README.md, src/parser.py, vector_database.txt, src/utils/strings.py, README.md, src/cli.py, photosynthesis.txt
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: vector, real number, embedding / expected any of: vector, real number, real-valued, real value, embedding, numeric
- Latency: 0.5s

### PASS - word_embedding.txt
- **Q:** What property of words is captured by their embedding vectors?
- **A:** The representation of a word is a real-valued vector that encodes the meaning of the word in such a way that the words that are closer in the vector space are expected to be similar in meaning. (word_embedding.txt)
- Sources: word_embedding.txt, vector_database.txt, rag.txt, src/parser.py, docs/architecture.html, src/utils/strings.py, src/cli.py, README.md, README.md, README.md, photosynthesis.txt
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: meaning, similar / expected any of: meaning, semantic, similar, context, syntactic, distribution
- Latency: 0.61s

### PASS - photosynthesis.txt
- **Q:** What gas does photosynthesis release as a byproduct?
- **A:** Oxygen (Source: photosynthesis.txt)
- Sources: photosynthesis.txt, docs/architecture.html, src/cli.py, rag.txt, src/utils/strings.py, src/parser.py, README.md, README.md, README.md, vector_database.txt, word_embedding.txt
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: oxygen / expected any of: oxygen
- Latency: 0.36s

### PASS - photosynthesis.txt
- **Q:** What kind of energy do photosynthetic organisms convert during photosynthesis?
- **A:** Light energy, typically from sunlight (photosynthesis.txt).
- Sources: photosynthesis.txt, docs/architecture.html, src/parser.py, src/utils/strings.py, README.md, rag.txt, README.md, README.md, src/cli.py, vector_database.txt, word_embedding.txt
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: light, sunlight / expected any of: light, sunlight, chemical
- Latency: 0.33s

### PASS - OOC
- **Q:** What are the typical symptoms of malaria in humans?
- **A:** The documents do not cover this topic.
- Sources: docs/architecture.html, README.md, src/cli.py, README.md, photosynthesis.txt, README.md, rag.txt, src/utils/strings.py, src/parser.py, vector_database.txt, word_embedding.txt
- Refused: True
- Latency: 0.34s

### PASS - OOC
- **Q:** Who won the FIFA World Cup in 2022?
- **A:** The documents do not cover it.
- Sources: README.md, src/parser.py, docs/architecture.html, src/cli.py, rag.txt, src/utils/strings.py, README.md, README.md, photosynthesis.txt, vector_database.txt, word_embedding.txt
- Refused: True
- Latency: 0.33s

### PASS - mini_parser
- **Q:** What transformation does the slugify helper apply to its input string?
- **A:** The `slugify` helper applies two transformations to its input string:

1. Lowercase: It converts the input string to lowercase.
2. Replace whitespace with hyphens: It replaces any runs of whitespace characters in the string with a single hyphen (-). (Source: src/utils/strings.py)
- Sources: src/utils/strings.py, src/cli.py, docs/architecture.html, README.md, rag.txt, README.md, src/parser.py, README.md, word_embedding.txt, photosynthesis.txt, vector_database.txt
- Top source: src/utils/strings.py (expected src/utils/strings.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: lowercase, lower, hyphen, whitespace / expected any of: lowercase, lower, hyphen, whitespace
- Latency: 0.74s

### PASS - mini_parser
- **Q:** What does parse_sentence do in the mini_parser project?
- **A:** The `parse_sentence` function (src/parser.py) splits a sentence into whitespace-separated tokens after stripping punctuation. It returns an ordered list of alphanumeric tokens. (1)
- Sources: src/parser.py, docs/architecture.html, README.md, src/cli.py, README.md, README.md, src/utils/strings.py, rag.txt, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: src/parser.py (expected src/parser.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: token, whitespace, punctuation, split / expected any of: token, whitespace, punctuation, split
- Latency: 0.55s

### PASS - mini_parser
- **Q:** According to the README, how do you run the mini_parser project from the command line?
- **A:** To run the mini_parser project from the command line, use:

```
python -m mini_parser.cli "Hello World"
```

(Source: README.md)
- Sources: README.md, docs/architecture.html, src/cli.py, README.md, README.md, src/parser.py, src/utils/strings.py, rag.txt, word_embedding.txt, photosynthesis.txt, vector_database.txt
- Top source: README.md (expected README.md) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: python -m mini_parser.cli, mini_parser.cli / expected any of: python -m mini_parser.cli, mini_parser.cli
- Latency: 0.52s

### PASS - mini_parser
- **Q:** What three layers are described in the architecture document?
- **A:** The Mini Parser project is split into three layers:

1. cli — the entry point. Parses command-line arguments and orchestrates the pipeline.
2. parser — splits sentences into tokens via the parse_sentence function. Strips punctuation before tokenising.
3. utils.strings — hosts the slugify helper that lowercases its input and replaces whitespace with hyphens.

(Source: docs/architecture.html)
- Sources: docs/architecture.html, README.md, rag.txt, README.md, README.md, src/parser.py, src/cli.py, photosynthesis.txt, src/utils/strings.py, word_embedding.txt, vector_database.txt
- Top source: docs/architecture.html (expected docs/architecture.html) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: cli, parser, utils / expected any of: cli, parser, utils
- Latency: 0.86s

### PASS - mini_parser
- **Q:** Which Python standard-library module does the mini_parser CLI import to parse arguments?
- **A:** argparse (src/cli.py)
- Sources: src/cli.py, README.md, docs/architecture.html, src/parser.py, README.md, src/utils/strings.py, README.md, rag.txt, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: src/cli.py (expected src/cli.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: argparse / expected any of: argparse
- Latency: 0.34s

### PASS - mini_parser
- **Q:** Which two `str` methods does parse_sentence call on each character to decide whether to keep it or replace it with whitespace?
- **A:** The document excerpt from `(src/parser.py)` describes `parse_sentence`. It uses the following code:

```python
cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
```

Here, it checks each character `ch` with two methods:

1. `ch.isalnum()`
2. `ch.isspace()`
- Sources: src/parser.py, src/cli.py, docs/architecture.html, src/utils/strings.py, README.md, README.md, README.md, rag.txt, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: src/parser.py (expected src/parser.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: isalnum, isspace / expected any of: isalnum, isspace
- Latency: 0.85s

### PASS - mini_parser
- **Q:** Which attribute of the parsed argparse namespace does cli.py pass to parse_sentence?
- **A:** The parsed argparse namespace's "text" attribute is passed to parse_sentence in src/cli.py (1).

@parser.add_argument("text", help="Sentence to slugify")
args = parser.parse_args()
tokens = parse_sentence(args.text)
- Sources: src/cli.py, src/parser.py, docs/architecture.html, README.md, README.md, src/utils/strings.py, README.md, rag.txt, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: src/cli.py (expected src/cli.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: args.text, "text" / expected any of: args.text, text attribute, "text", 'text'
- Latency: 0.65s

### PASS - mini_parser
- **Q:** How does slugify split its input into pieces before joining them with hyphens?
- **A:** The `slugify` function splits the input string by whitespace using the `split()` method, then joins the resulting list of tokens with hyphens using the `join()` method. (src/utils/strings.py)

Specifically, it uses the following line to split the input:
```python
value.lower().split()
```
This converts the input string to lowercase and splits it into a list of whitespace-separated tokens.

Then, it joins these tokens with hyphens using this line:
```python
"-".join(value.lower().split())
```
So, the final output is a string where each token from the original input is separated by a hyphen.
- Sources: src/utils/strings.py, docs/architecture.html, src/cli.py, README.md, src/parser.py, README.md, rag.txt, README.md, word_embedding.txt, photosynthesis.txt, vector_database.txt
- Top source: src/utils/strings.py (expected src/utils/strings.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: split, whitespace / expected any of: split, whitespace
- Latency: 1.28s

### PASS - mini_parser
- **Q:** According to the README, what does the mini_parser project exist as?
- **A:** A tiny command-line tool that turns a sentence into a URL-friendly slug. It exists as a small example project paired with its own documentation for end-to-end testing. (README.md)
- Sources: README.md, docs/architecture.html, src/cli.py, README.md, README.md, src/parser.py, rag.txt, src/utils/strings.py, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: README.md (expected README.md) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: example project, end-to-end testing, paired with, documentation / expected any of: example project, end-to-end testing, paired with, documentation
- Latency: 0.56s

### PASS - mini_parser
- **Q:** According to the architecture document, in which direction does data flow through the three layers?
- **A:** Data flows linearly from the CLI layer, through the parser layer, to the utils layer; there are no cycles or side effects beyond stdout writes. (docs/architecture.html)
- Sources: docs/architecture.html, README.md, README.md, rag.txt, README.md, src/cli.py, src/parser.py, src/utils/strings.py, vector_database.txt, photosynthesis.txt, word_embedding.txt
- Top source: docs/architecture.html (expected docs/architecture.html) -> OK
- Top kind: doc (expected doc) -> OK
- Matched: linearly, from the cli, no cycles / expected any of: linearly, from the cli, no cycles, no side effects
- Latency: 0.55s

### PASS - mini_parser
- **Q:** From which module does the mini_parser CLI import the slugify helper?
- **A:** src/utils/strings.py (utils.strings) is imported from by src/cli.py (the Mini Parser fixture).
- Sources: src/cli.py, src/utils/strings.py, docs/architecture.html, README.md, README.md, README.md, src/parser.py, rag.txt, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: src/cli.py (expected src/cli.py) -> OK
- Top kind: code (expected code) -> OK
- Matched: utils.strings, utils/strings / expected any of: utils.strings, utils/strings, .utils.strings
- Latency: 0.45s

### PASS - OOC
- **Q:** Does the mini_parser project document any retry behaviour on network failures?
- **A:** The documents do not cover it.
- Sources: docs/architecture.html, README.md, src/cli.py, src/parser.py, README.md, src/utils/strings.py, README.md, rag.txt, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Refused: True
- Latency: 0.34s

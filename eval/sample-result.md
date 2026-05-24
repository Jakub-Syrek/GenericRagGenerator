# RAG eval - 20260524-115326

- Total questions: **12** (in-corpus 10, OOC 2)
- Passed (composite): **12** / 12
- Retrieval top-1 precision: **1.0**
- Answer substring match: **1.0**
- OOC refusal rate: **1.0**
- Average latency: **0.44s**

## Per-question results

### PASS - rag.txt
- **Q:** What does RAG stand for?
- **A:** RAG stands for "Retrieval-augmented generation" (Source: rag.txt).
- Sources: rag.txt, photosynthesis.txt, vector_database.txt, word_embedding.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: retrieval-augmented generation / expected any of: retrieval-augmented generation, retrieval augmented generation
- Latency: 0.89s

### PASS - rag.txt
- **Q:** What kind of model does RAG combine retrieval with?
- **A:** RAG combines retrieval with large language models (LLMs). (Source: rag.txt)
- Sources: rag.txt, vector_database.txt, word_embedding.txt, photosynthesis.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: language model, llm / expected any of: language model, generative, llm
- Latency: 0.35s

### PASS - rag.txt
- **Q:** Why would someone use RAG instead of a plain language model?
- **A:** According to the document (rag.txt), the main reason to use Retrieval-augmented generation (RAG) is that it allows large language models (LLMs) to "use domain-specific and/or updated information that is not available in the training data". This enables LLMs, such as chatbots, to access internal company data or generate responses based on authoritative sources.
- Sources: rag.txt, word_embedding.txt, vector_database.txt, photosynthesis.txt
- Top source: rag.txt (expected rag.txt) -> OK
- Matched: updated, domain-specific, training data / expected any of: up-to-date, current, updated, private, external, domain-specific, training data, factual, hallucin
- Latency: 0.82s

### PASS - vector_database.txt
- **Q:** What kind of data does a vector database store?
- **A:** A vector database stores embeddings of data in vector space (Source: vector_database.txt).
- Sources: vector_database.txt, rag.txt, word_embedding.txt, photosynthesis.txt
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: vector, embedding / expected any of: vector, embedding, high-dimensional, high dimensional
- Latency: 0.36s

### PASS - vector_database.txt
- **Q:** What kind of search do vector databases enable?
- **A:** Vector databases enable similarity search, semantic search, multi-modal search, recommendations engines, object detection, and retrieval-augmented generation (RAG) (vector_database.txt).
- Sources: vector_database.txt, rag.txt, word_embedding.txt, photosynthesis.txt
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: similarity, semantic / expected any of: similarity, nearest neighbor, semantic
- Latency: 0.41s

### PASS - vector_database.txt
- **Q:** Name one common application of vector databases.
- **A:** One common application of vector databases is "recommendations engines" (vector_database.txt).
- Sources: vector_database.txt, rag.txt, word_embedding.txt, photosynthesis.txt
- Top source: vector_database.txt (expected vector_database.txt) -> OK
- Matched: recommendation / expected any of: recommendation, search, retrieval, rag, image, machine learning
- Latency: 0.27s

### PASS - word_embedding.txt
- **Q:** In word embeddings, what are words mapped to?
- **A:** Words or phrases from the vocabulary are mapped to vectors of real numbers (word_embedding.txt).
- Sources: word_embedding.txt, rag.txt, vector_database.txt, photosynthesis.txt
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: vector, real number, embedding / expected any of: vector, real number, real-valued, real value, embedding, numeric
- Latency: 0.37s

### PASS - word_embedding.txt
- **Q:** What property of words is captured by their embedding vectors?
- **A:** The representation is a real-valued vector that encodes the meaning of the word in such a way that the words that are closer in the vector space are expected to be similar in meaning. (word_embedding.txt)
- Sources: word_embedding.txt, vector_database.txt, rag.txt, photosynthesis.txt
- Top source: word_embedding.txt (expected word_embedding.txt) -> OK
- Matched: meaning, similar / expected any of: meaning, semantic, similar, context, syntactic, distribution
- Latency: 0.54s

### PASS - photosynthesis.txt
- **Q:** What gas does photosynthesis release as a byproduct?
- **A:** According to "photosynthesis.txt", oxygen (O2) is released as a byproduct of water splitting during oxygenic photosynthesis. (Source: photosynthesis.txt)
- Sources: photosynthesis.txt, rag.txt, vector_database.txt, word_embedding.txt
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: oxygen / expected any of: oxygen
- Latency: 0.5s

### PASS - photosynthesis.txt
- **Q:** What kind of energy do photosynthetic organisms convert during photosynthesis?
- **A:** Light energy (typically from sunlight) is converted into chemical energy during photosynthesis. (Source: photosynthesis.txt)
- Sources: photosynthesis.txt, rag.txt, vector_database.txt, word_embedding.txt
- Top source: photosynthesis.txt (expected photosynthesis.txt) -> OK
- Matched: light, sunlight, chemical / expected any of: light, sunlight, chemical
- Latency: 0.34s

### PASS - OOC
- **Q:** What are the typical symptoms of malaria in humans?
- **A:** The documents do not cover it.
- Sources: photosynthesis.txt, rag.txt, vector_database.txt, word_embedding.txt
- Refused: True
- Latency: 0.18s

### PASS - OOC
- **Q:** Who won the FIFA World Cup in 2022?
- **A:** The documents do not cover it.
- Sources: rag.txt, photosynthesis.txt, vector_database.txt, word_embedding.txt
- Refused: True
- Latency: 0.27s

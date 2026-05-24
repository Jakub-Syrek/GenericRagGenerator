# RAG eval - 20260524-114028

- Total questions: **6**
- Passed: **6**
- Failed: **0**
- Average latency: **0.51s**

## Per-question results

### PASS - retrieval_augmented_generation.txt
- **Q:** What does RAG stand for?
- **A:** According to the document excerpts, RAG stands for "Retrieval-augmented generation" (Source: retrieval_augmented_generation.txt)
- Sources: retrieval_augmented_generation.txt, vector_database.txt
- Matched: retrieval-augmented generation / expected any of: retrieval-augmented generation, retrieval augmented generation
- Latency: 1.13s

### PASS - retrieval_augmented_generation.txt
- **Q:** What kind of model does RAG combine retrieval with?
- **A:** The document doesn't specify the type of model that RAG combines retrieval with. It only mentions that it is a technique used by "large language models (LLMs)" and provides an example involving LLM-based chatbots, but it does not explicitly state what kind of model it combines with.

( retrieval_augmented_generation.txt )
- Sources: retrieval_augmented_generation.txt, vector_database.txt
- Matched: language model, llm / expected any of: language model, generative, llm
- Latency: 0.68s

### PASS - retrieval_augmented_generation.txt
- **Q:** What is one benefit of using RAG over a plain language model?
- **A:** One benefit of using RAG over a plain language model is that it allows large language models to use domain-specific and/or updated information that is not available in the training data. (retrieval_augmented_generation.txt)
- Sources: retrieval_augmented_generation.txt, vector_database.txt
- Matched: updated, domain-specific, training data / expected any of: up-to-date, current, updated, private, external, domain-specific, training data, factual, hallucin
- Latency: 0.47s

### PASS - vector_database.txt
- **Q:** What does a vector database store?
- **A:** A vector database stores embeddings of data in vector space (vector_database.txt).
- Sources: vector_database.txt, retrieval_augmented_generation.txt
- Matched: vector, embedding / expected any of: vector, embedding, high-dimensional, high dimensional
- Latency: 0.25s

### PASS - vector_database.txt
- **Q:** What kind of search do vector databases enable?
- **A:** Vector databases implement approximate nearest neighbor algorithms to enable semantic similarity search (Source: vector_database.txt).
- Sources: vector_database.txt, retrieval_augmented_generation.txt
- Matched: similarity, nearest neighbor, semantic / expected any of: similarity, nearest neighbor, semantic
- Latency: 0.27s

### PASS - vector_database.txt
- **Q:** Name one common application of vector databases.
- **A:** One common application of vector databases is similarity search (Source: vector_database.txt).
- Sources: vector_database.txt, retrieval_augmented_generation.txt
- Matched: search / expected any of: recommendation, search, retrieval, rag, image, machine learning
- Latency: 0.24s

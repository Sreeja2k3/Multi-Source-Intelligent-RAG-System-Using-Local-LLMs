# Multi-Source-Intelligent-RAG-System-Using-Local-LLMs
-What This Is
Most RAG demos lock you into a single document type and depend on OpenAI's API — meaning your data leaves your machine and your costs scale with usage.
This system solves both problems. It ingests heterogeneous knowledge sources (PDFs, live URLs, YouTube transcripts, plain text) through a unified pipeline, embeds them into a shared FAISS vector index, and answers queries using Llama 3 running entirely on local hardware via Ollama — no API keys, no internet required at inference time, no data exposure.

-Pipeline Architecture
1. Ingestion
Source-specific loaders parse each input type — PyPDFLoader for PDFs, WebBaseLoader for URLs, YoutubeLoader for transcripts, and direct text input — normalizing all content into LangChain Document objects.
2. Chunking
Documents are split using source-aware parameters. PDFs use larger chunks with higher overlap to preserve paragraph context; YouTube transcripts use smaller chunks to avoid mid-sentence breaks across timestamp boundaries.
3. Embedding
Each chunk is encoded using HuggingFace's all-MiniLM-L6-v2 running entirely locally — no API call, no data leaving the machine.
4. Indexing
Embeddings are stored in a FAISS index with source metadata preserved per chunk, enabling citation tracking at retrieval time.
5. Retrieval
User queries are embedded with the same model, and top-k semantically similar chunks are retrieved from FAISS.
6. Generation
Retrieved context is passed to Llama 3 via Ollama through a LangChain retrieval chain. The model is instructed to answer strictly from context — no hallucination from parametric memory.
7. Response
Answer is displayed in Streamlit alongside the source chunks and their origin (document name, page, or timestamp).

-Key Design Decisions
Why local inference (Ollama + Llama 3)?
Sending documents to a cloud LLM means your data is processed on someone else's server. For sensitive domains — legal, medical, financial, internal enterprise — that's a non-starter. Running inference entirely on-device eliminates that surface area entirely.
Why FAISS over a managed vector DB?
No server to spin up, no network latency, no cost. FAISS runs in-process, making this fully self-contained. For a single-user local system, it's the right tradeoff.
Why custom chunking logic?
PDFs, web pages, and YouTube transcripts have fundamentally different structure. A flat chunking strategy degrades retrieval quality. The pipeline applies source-aware chunking — different chunk sizes and overlap ratios depending on content type — to preserve semantic coherence per source.

-Tech Stack
ComponentTechnologyRoleLLM InferenceOllama + Llama 3Local, offline generationEmbeddingsHuggingFace all-MiniLM-L6-v2Semantic vector encodingVector StoreFAISSHigh-speed similarity searchOrchestrationLangChainPipeline & retrieval chainDocument LoadersLangChain community loadersPDF, URL, YouTube, textUIStreamlitInteractive frontendLanguagePython 3.10+—

Getting Started
-Prerequisites

Python 3.10+
Ollama installed and running
Llama 3 pulled: ollama pull llama3

-Installation
bashgit clone https://github.com/YOUR_USERNAME/multi-source-rag.git
cd multi-source-rag
pip install -r requirements.txt
Run
bashstreamlit run app.py
Open http://localhost:8501, load your sources, and start querying.

-How It Works — Step by Step

Ingest — Choose one or more sources: upload a PDF, paste a URL, enter a YouTube link, or type raw text directly.
Process — Each source is parsed by a dedicated loader, chunked using source-aware parameters, and embedded using MiniLM.
Index — Chunks are stored in a FAISS index with metadata (source type, page/timestamp, original text).
Query — Your question is embedded, top-k semantically similar chunks are retrieved, and the context is passed to Llama 3.
Answer — The model responds using only the retrieved context. Source citations are displayed alongside every answer.


-What I Learned Building This

Chunking strategy has an outsized impact on retrieval quality — poorly chunked documents produce coherent-sounding but contextually wrong answers.
all-MiniLM-L6-v2 punches well above its size for semantic similarity on domain-specific content.
YouTube transcript retrieval requires careful timestamp-aware chunking to avoid mid-sentence context breaks.
LangChain's abstraction is convenient but adds latency — understanding what's happening beneath the chain matters for debugging.


-Limitations 

Single-user, local only — not architected for concurrent users or cloud deployment in current form.
No persistent index — the vector store resets per session; persistence would require serializing the FAISS index to disk between runs.
Llama 3 performance is hardware-dependent — inference speed varies significantly by available RAM and whether a GPU is present.
No authentication or access control — not suitable for multi-user environments without additional work.


-Roadmap

 Persist FAISS index across sessions
 Add support for .docx and .csv sources
 Implement re-ranking (MMR or cross-encoder) for improved retrieval precision
 Explore quantized models for lower-memory hardware
 Add conversation memory for multi-turn Q&A


License
MIT — use it, extend it, break it.

Built to explore privacy-preserving, locally-hosted RAG pipelines as a serious alternative to cloud-dependent LLM systems.

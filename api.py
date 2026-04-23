# api.py
# FastAPI backend for the RAG system.
#
# WHY FASTAPI MATTERS FOR YOUR RESUME:
# Streamlit is a demo tool. FastAPI is how real AI products are built.
# Adding this means your RAG system is now a proper API that any
# frontend, mobile app, or service can call.
#
# WHAT THIS GIVES YOU:
# - POST /query        → ask a question, get an answer + sources
# - POST /ingest/url   → index a URL
# - POST /ingest/file  → upload and index a PDF/DOCX/TXT
# - GET  /stats        → how many chunks are indexed
# - GET  /health       → is the server alive?
#
# HOW TO RUN:
#   pip install fastapi uvicorn python-multipart
#   uvicorn api:app --reload --port 8000
#
# HOW TO TEST (in browser):
#   http://localhost:8000/docs   ← auto-generated interactive API docs
#
# Interview Q: "What is FastAPI?"
# → A modern Python web framework for building APIs. Faster than Flask,
#   auto-generates documentation, uses type hints for validation.
# Interview Q: "What is an API endpoint?"
# → A URL that accepts requests and returns responses. Like a function
#   you can call over the internet.

import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from src.retrieval.vector_store import VectorStoreManager
from src.ingestion.pipeline import IngestionPipeline
from src.generation.rag_chain import RAGChain

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Multi-Source RAG API",
    description="Query AI research papers and documents using local LLM inference.",
    version="1.0.0",
)

# CORS — allows the Streamlit UI (or any frontend) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize RAG components once at startup ─────────────────────────────────
# These are expensive to initialize (loads embedding model, connects to ChromaDB)
# so we do it once when the server starts, not on every request.
logger.info("Initializing RAG system...")
vs = VectorStoreManager().create_or_load()
pipeline = IngestionPipeline(vs)
rag = RAGChain(vs)
logger.success("RAG system ready.")


# ── Request / Response models ─────────────────────────────────────────────────
# Pydantic models define exactly what JSON the API accepts and returns.
# FastAPI uses these for automatic validation and documentation.
# Interview Q: "What is Pydantic?" → Data validation library. Define a model,
# FastAPI automatically validates incoming JSON against it.

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5
    chat_history: Optional[list[ChatMessage]] = None
    source_filter: Optional[str] = None  # filter by file name or source type

class SourceItem(BaseModel):
    source_type: str
    file_name: Optional[str] = None
    url: Optional[str] = None
    chunk_index: Optional[int] = None

class QueryResponse(BaseModel):
    question: str
    answer: str
    num_sources: int
    sources: list[SourceItem]

class IngestURLRequest(BaseModel):
    url: str

class IngestResponse(BaseModel):
    message: str
    chunks_indexed: int

class StatsResponse(BaseModel):
    total_chunks: int
    collection: str

class HealthResponse(BaseModel):
    status: str
    model: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Check if the API is running and which model is loaded."""
    return {"status": "ok", "model": rag.llm.model}


@app.get("/stats", response_model=StatsResponse)
def get_stats():
    """Return how many document chunks are currently indexed."""
    return vs.get_collection_stats()


@app.get("/sources")
def get_sources():
    """Return list of unique source names in the index."""
    return {"sources": vs.get_source_list()}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    Ask a question. Returns an answer generated from indexed documents.

    Example request body:
    {
        "question": "How does the attention mechanism work?",
        "top_k": 5
    }
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    stats = vs.get_collection_stats()
    if stats["total_chunks"] == 0:
        raise HTTPException(
            status_code=400,
            detail="No documents indexed. Use /ingest/url or /ingest/file first."
        )

    logger.info(f"Query: {request.question}")

    # Build metadata filter if source_filter is provided
    filter_dict = None
    if request.source_filter:
        filter_dict = {"file_name": request.source_filter}

    # Pass chat history for conversation memory
    history = None
    if request.chat_history:
        history = [{"role": m.role, "content": m.content} for m in request.chat_history]

    result = rag.query(request.question, chat_history=history)

    # Format sources for the response
    sources = []
    for doc in result["sources"]:
        meta = doc.metadata
        sources.append(SourceItem(
            source_type=meta.get("source_type", "unknown"),
            file_name=meta.get("file_name"),
            url=meta.get("url"),
            chunk_index=meta.get("chunk_index"),
        ))

    return QueryResponse(
        question=request.question,
        answer=result["answer"],
        num_sources=result["num_sources"],
        sources=sources,
    )


@app.post("/ingest/url", response_model=IngestResponse)
def ingest_url(request: IngestURLRequest):
    """
    Index a web page by URL.

    Example request body:
    {
        "url": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation"
    }
    """
    if not request.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    logger.info(f"Ingesting URL: {request.url}")
    try:
        n = pipeline.ingest_url(request.url)
        return IngestResponse(
            message=f"Successfully indexed {request.url}",
            chunks_indexed=n
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DeleteSourceRequest(BaseModel):
    source_name: str


@app.delete("/clear", response_model=IngestResponse)
def clear_index():
    """Delete ALL documents from the vector store."""
    n = vs.clear_collection()
    logger.warning(f"Cleared entire index: {n} chunks deleted")
    return IngestResponse(message=f"Cleared all documents", chunks_indexed=n)


@app.delete("/source", response_model=IngestResponse)
def delete_source(request: DeleteSourceRequest):
    """Delete all chunks from a specific source (by file name or URL)."""
    n = vs.delete_by_source(request.source_name)
    if n == 0:
        raise HTTPException(status_code=404, detail=f"No chunks found for source: {request.source_name}")
    return IngestResponse(message=f"Deleted source: {request.source_name}", chunks_indexed=n)

@app.post("/ingest/file", response_model=IngestResponse)
def ingest_file(file: UploadFile = File(...)):
    """
    Upload and index a PDF, DOCX, or TXT file.
    Send as multipart/form-data with key 'file'.
    """
    suffix = Path(file.filename).suffix.lower()
    supported = [".pdf", ".docx", ".txt", ".csv", ".json"]
    if suffix not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Use: {', '.join(supported)}"
        )

    # Save to a temp directory under the ORIGINAL filename so that
    # metadata["file_name"] (derived from the path by the loader) shows
    # the real name instead of a random tmpXXXX.pdf.
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    with open(tmp_path, "wb") as f:
        f.write(file.file.read())

    try:
        logger.info(f"Ingesting file: {file.filename}")
        ingest_map = {
            ".pdf": pipeline.ingest_pdf,
            ".docx": pipeline.ingest_docx,
            ".txt": pipeline.ingest_txt,
            ".csv": pipeline.ingest_csv,
            ".json": pipeline.ingest_json,
        }
        n = ingest_map[suffix](tmp_path)

        return IngestResponse(
            message=f"Successfully indexed {file.filename}",
            chunks_indexed=n
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the temp file and its directory
        try:
            os.unlink(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


@app.post("/ingest/youtube", response_model=IngestResponse)
def ingest_youtube(request: IngestURLRequest):
    """
    Index a YouTube video transcript by URL.

    Example request body:
    {
        "url": "https://youtube.com/watch?v=..."
    }
    """
    logger.info(f"Ingesting YouTube: {request.url}")
    try:
        n = pipeline.ingest_youtube(request.url)
        return IngestResponse(
            message=f"Successfully indexed YouTube video",
            chunks_indexed=n
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from src.database.db_manager import DatabaseManager
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

# ── Initialize RAG & DB components once at startup ─────────────────────────────────
logger.info("Initializing RAG database and system...")
db = DatabaseManager()
vs = VectorStoreManager().create_or_load()
pipeline = IngestionPipeline(vs)
rag = RAGChain(vs)
logger.success("RAG database and system ready.")


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
    conversation_id: Optional[str] = None  # V2 Addition for DB persistence

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
    message_id: Optional[int] = None  # V2 Addition to allow ratings/feedback

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

class CreateConvRequest(BaseModel):
    id: str
    title: Optional[str] = "New Chat"

class FeedbackRequest(BaseModel):
    feedback: Optional[str] = None  # "up", "down", or None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Check if the API is running and which model is loaded."""
    return {"status": "ok", "model": rag.model_name}


@app.get("/stats", response_model=StatsResponse)
def get_stats():
    """Return how many document chunks are currently indexed."""
    return vs.get_collection_stats()


@app.get("/sources")
def get_sources():
    """Return list of unique source names in the index."""
    return {"sources": vs.get_source_list()}


# ── V2 SQLite Database Endpoints ──────────────────────────────────────────────

@app.get("/conversations")
def get_conversations():
    """Return list of all chat sessions saved in the SQLite database."""
    return db.get_conversations()


@app.post("/conversations")
def create_conversation(request: CreateConvRequest):
    """Create a new chat session database entry."""
    success = db.create_conversation(request.id, request.title)
    if not success:
        raise HTTPException(status_code=400, detail=f"Conversation ID '{request.id}' already exists.")
    return {"message": "Conversation created successfully", "id": request.id}


@app.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """Delete a chat session and all messages from the SQLite database."""
    success = db.delete_conversation(conv_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found.")
    return {"message": f"Deleted conversation '{conv_id}'"}


@app.get("/conversations/{conv_id}/messages")
def get_conversation_messages(conv_id: str):
    """Fetch history list of messages and sources for a conversation."""
    return db.get_conversation_messages(conv_id)


@app.post("/messages/{message_id}/feedback")
def set_message_feedback(message_id: int, request: FeedbackRequest):
    """Record user thumbs up/down rating for an assistant response."""
    try:
        success = db.set_message_feedback(message_id, request.feedback)
        if not success:
            raise HTTPException(status_code=404, detail=f"Message ID {message_id} not found.")
        return {"message": "Feedback recorded successfully", "feedback": request.feedback}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/ingestion/logs")
def get_ingestion_logs():
    """Fetch upload and ingestion logs for dashboard monitoring."""
    return db.get_ingestion_logs()


@app.get("/db/stats")
def get_db_stats():
    """Fetch telemetry counts from relational database."""
    return db.get_system_stats()


# ── RAG Pipeline Endpoints ───────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    Ask a question. Returns an answer generated from indexed documents.
    If conversation_id is provided, saves chat messages and sources to SQLite DB.
    """
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")



    logger.info(f"Query: {request.question}")

    # Build metadata filter if source_filter is provided
    filter_dict = None
    if request.source_filter and request.source_filter != "All Sources":
        filter_dict = {"file_name": request.source_filter}

    # Save user query to DB if conversation is active
    if request.conversation_id:
        db.add_message(request.conversation_id, "user", request.question)

    # Fetch context history: Prefer request.chat_history, otherwise load from DB
    history = None
    if request.chat_history:
        history = [{"role": m.role, "content": m.content} for m in request.chat_history]
    elif request.conversation_id:
        past_msgs = db.get_conversation_messages(request.conversation_id)
        # Exclude the user message we just inserted at the end of the history
        history = [{"role": m["role"], "content": m["content"]} for m in past_msgs[:-1]]

    # Execute RAG query and measure response time
    start_time = time.time()
    try:
        result = rag.query(request.question, chat_history=history)
    except Exception as e:
        logger.error(f"Failed to generate RAG response: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    elapsed = time.time() - start_time

    # Save assistant response and sources references to DB
    assistant_msg_id = None
    if request.conversation_id:
        assistant_msg_id = db.add_message(request.conversation_id, "assistant", result["answer"], elapsed)
        for doc in result["sources"]:
            meta = doc.metadata
            db.add_source(
                assistant_msg_id,
                source_type=meta.get("source_type", "unknown"),
                file_name=meta.get("file_name"),
                url=meta.get("url")
            )

    # Format sources list response
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
        message_id=assistant_msg_id
    )


@app.post("/ingest/url", response_model=IngestResponse)
def ingest_url(request: IngestURLRequest):
    """Index a web page by URL."""
    if not request.url.strip():
        raise HTTPException(status_code=400, detail="URL cannot be empty.")

    logger.info(f"Ingesting URL: {request.url}")
    try:
        n = pipeline.ingest_url(request.url)
        db.log_ingestion(
            file_name=request.url,
            source_type="web",
            file_size=0,
            chunk_count=n,
            status="success"
        )
        return IngestResponse(
            message=f"Successfully indexed {request.url}",
            chunks_indexed=n
        )
    except Exception as e:
        db.log_ingestion(
            file_name=request.url,
            source_type="web",
            status="failed",
            error_message=str(e)
        )
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

    # Save to a temp directory under the ORIGINAL filename
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)
    
    # Read file and measure size
    file_bytes = file.file.read()
    file_size = len(file_bytes)
    
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)

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

        db.log_ingestion(
            file_name=file.filename,
            source_type=suffix.replace(".", ""),
            file_size=file_size,
            chunk_count=n,
            status="success"
        )
        return IngestResponse(
            message=f"Successfully indexed {file.filename}",
            chunks_indexed=n
        )
    except Exception as e:
        db.log_ingestion(
            file_name=file.filename,
            source_type=suffix.replace(".", ""),
            file_size=file_size,
            status="failed",
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(tmp_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass


@app.post("/ingest/youtube", response_model=IngestResponse)
def ingest_youtube(request: IngestURLRequest):
    """Index a YouTube video transcript by URL."""
    logger.info(f"Ingesting YouTube: {request.url}")
    try:
        n = pipeline.ingest_youtube(request.url)
        db.log_ingestion(
            file_name=request.url,
            source_type="youtube",
            file_size=0,
            chunk_count=n,
            status="success"
        )
        return IngestResponse(
            message=f"Successfully indexed YouTube video",
            chunks_indexed=n
        )
    except Exception as e:
        db.log_ingestion(
            file_name=request.url,
            source_type="youtube",
            status="failed",
            error_message=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))

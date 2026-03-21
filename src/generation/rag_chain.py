# src/generation/rag_chain.py
#
# V2 CHANGE: Removed LCEL pipe-chain (|) syntax.
# Replaced with explicit step-by-step function calls.
# WHY: LCEL is cleaner but harder to debug when something breaks.
# Explicit calls make it obvious exactly which step failed.
# This is better for learning AND for debugging in interviews.

from typing import List
from loguru import logger
from langchain_core.documents import Document
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import settings
from src.retrieval.vector_store import VectorStoreManager


SYSTEM_PROMPT = """You are a helpful assistant that answers questions using ONLY the provided context.
If the answer is not in the context, say: "I don't have enough information in the provided documents to answer this."
Do not use any knowledge outside of the context provided. Be concise and accurate."""


def format_context(docs: List[Document]) -> str:
    """Format retrieved docs into a context string for the prompt."""
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata
        source_type = meta.get("source_type", "unknown")

        if source_type == "pdf":
            label = f"PDF: {meta.get('file_name', '?')} | Page: {meta.get('page', '?')}"
        elif source_type == "docx":
            label = f"DOCX: {meta.get('file_name', '?')}"
        elif source_type == "web":
            label = f"Web: {meta.get('url', '?')}"
        elif source_type == "youtube":
            label = f"YouTube: {meta.get('url', '?')}"
        else:
            label = f"Source: {meta.get('source', '?')}"

        parts.append(f"[Document {i} — {label}]\n{doc.page_content}")

    return "\n\n---\n\n".join(parts)


class RAGChain:

    def __init__(self, vector_store_manager: VectorStoreManager):
        self.vs = vector_store_manager
        # ChatOllama from langchain-ollama package
        # Make sure Ollama is running: `ollama serve`
        # Make sure model is pulled: `ollama pull llama3.2`
        self.llm = ChatOllama(
            model=settings.LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
            num_predict=settings.LLM_MAX_TOKENS,
        )

    def query(self, question: str) -> dict:
        # Step 1: Retrieve relevant chunks
        retriever = self.vs.get_retriever()
        docs = retriever.invoke(question)
        logger.info(f"Retrieved {len(docs)} chunks for query: {question}")

        if not docs:
            return {
                "answer": "No relevant documents found. Please index some documents first.",
                "sources": [],
                "num_sources": 0,
            }

        # Step 2: Format context from retrieved docs
        context = format_context(docs)

        # Step 3: Build prompt and call LLM
        user_message = f"Context:\n{context}\n\nQuestion: {question}"
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        # Step 4: Call local LLM
        response = self.llm.invoke(messages)
        answer = response.content  # .content extracts the text string

        logger.success(f"Generated answer ({len(answer)} chars)")
        return {
            "answer": answer,
            "sources": docs,
            "num_sources": len(docs),
        }

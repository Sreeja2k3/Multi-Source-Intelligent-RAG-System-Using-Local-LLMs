# src/generation/rag_chain.py
#
# V2 CHANGE: Removed LCEL pipe-chain (|) syntax.
# Replaced with explicit step-by-step function calls.
# WHY: LCEL is cleaner but harder to debug when something breaks.
# Explicit calls make it obvious exactly which step failed.
# This is better for learning AND for debugging in interviews.

from typing import List, Optional
from loguru import logger
from langchain_core.documents import Document
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from src.config import settings
from src.retrieval.vector_store import VectorStoreManager


SYSTEM_PROMPT = """You are a knowledgeable assistant. Answer the user's question using the provided context.

Rules:
- Answer directly and naturally, as if you're explaining to a colleague.
- NEVER say "According to the provided context", "Based on Document 1", or reference document numbers.
- NEVER mention that you were given context or documents. Just answer the question.
- If the context doesn't contain the answer, say: "I don't have enough information to answer this."
- Be concise. Get to the point. No filler phrases.
- If the context contains specific names, numbers, or facts, use them precisely."""


def format_context(docs: List[Document]) -> str:
    """Format retrieved docs into a context string for the prompt."""
    parts = []
    for doc in docs:
        parts.append(doc.page_content)
    return "\n\n---\n\n".join(parts)


class RAGChain:

    def __init__(self, vector_store_manager: VectorStoreManager):
        self.vs = vector_store_manager
        self.llm = ChatOllama(
            model=settings.LLM_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=settings.LLM_TEMPERATURE,
            num_predict=settings.LLM_MAX_TOKENS,
        )

    def query(self, question: str, chat_history: Optional[List[dict]] = None) -> dict:
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

        # Step 2: Re-rank chunks using cross-encoder for better relevance
        if settings.USE_RERANKER:
            docs = self.vs.rerank(question, docs, top_k=settings.RETRIEVAL_TOP_K)
            logger.info(f"Re-ranked to {len(docs)} chunks")

        # Step 3: Format context from retrieved docs
        context = format_context(docs)

        # Step 4: Build prompt with conversation history
        user_message = f"Context:\n{context}\n\nQuestion: {question}"
        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        # Add conversation history if available
        if chat_history:
            for msg in chat_history[-settings.MEMORY_WINDOW:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_message))

        # Step 5: Call local LLM
        response = self.llm.invoke(messages)
        answer = response.content

        logger.success(f"Generated answer ({len(answer)} chars)")
        return {
            "answer": answer,
            "sources": docs,
            "num_sources": len(docs),
        }

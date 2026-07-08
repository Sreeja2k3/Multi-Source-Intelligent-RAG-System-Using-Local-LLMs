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

NO_CONTEXT_PROMPT = """You are Loca, a helpful and friendly private AI assistant. 
The user has not indexed or uploaded any documents to their knowledge base yet, so you do not have specific document context.
Answer their greeting or question generally using your own knowledge. 
Remind them gently that if they want to query specific documents (PDF, DOCX, TXT, CSV, JSON, Web URLs, or YouTube videos), they can upload them in the "Knowledge Base" tab."""


def format_context(docs: List[Document]) -> str:
    """Format retrieved docs into a context string for the prompt."""
    parts = []
    for doc in docs:
        parts.append(doc.page_content)
    return "\n\n---\n\n".join(parts)


class RAGChain:

    def __init__(self, vector_store_manager: VectorStoreManager):
        self.vs = vector_store_manager
        self.model_name = settings.LLM_MODEL
        
        if settings.LLM_PROVIDER == "openai":
            from langchain_openai import ChatOpenAI
            logger.info(f"Using Cloud OpenAI LLM: {settings.LLM_MODEL}")
            self.llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        elif settings.LLM_PROVIDER == "groq":
            from langchain_groq import ChatGroq
            logger.info(f"Using Cloud Groq LLM: {settings.LLM_MODEL}")
            self.llm = ChatGroq(
                model=settings.LLM_MODEL,
                api_key=settings.GROQ_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
        else:
            logger.info(f"Using Local Ollama LLM: {settings.LLM_MODEL}")
            self.llm = ChatOllama(
                model=settings.LLM_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=settings.LLM_TEMPERATURE,
                num_predict=settings.LLM_MAX_TOKENS,
            )

    def query(self, question: str, chat_history: Optional[List[dict]] = None) -> dict:
        # Step 1: Retrieve relevant chunks
        try:
            retriever = self.vs.get_retriever()
            docs = retriever.invoke(question)
            logger.info(f"Retrieved {len(docs)} chunks for query: {question}")
        except Exception as e:
            logger.warning(f"Retrieval skipped or failed (likely empty vector database): {e}")
            docs = []

        # Step 2: Re-rank chunks using cross-encoder for better relevance
        if docs and settings.USE_RERANKER:
            docs = self.vs.rerank(question, docs, top_k=settings.RETRIEVAL_TOP_K)
            logger.info(f"Re-ranked to {len(docs)} chunks")

        # Step 3: Call LLM with or without context
        messages = []
        if docs:
            # Build prompt with retrieved context
            context = format_context(docs)
            user_message = f"Context:\n{context}\n\nQuestion: {question}"
            messages.append(SystemMessage(content=SYSTEM_PROMPT))
        else:
            # Build general chatbot fallback prompt
            user_message = question
            messages.append(SystemMessage(content=NO_CONTEXT_PROMPT))

        # Add conversation history if available
        if chat_history:
            for msg in chat_history[-settings.MEMORY_WINDOW:]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_message))

        # Step 4: Call LLM
        response = self.llm.invoke(messages)
        answer = response.content

        logger.success(f"Generated answer ({len(answer)} chars)")
        return {
            "answer": answer,
            "sources": docs,
            "num_sources": len(docs),
        }

import os
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
        self.llm, self.model_name, self.provider = self._resolve_llm_client()

    def _resolve_llm_client(self):
        """Auto-detects keys, fixes provider mismatches, and instantiates the proper LLM."""
        groq_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")

        # Auto-fix swapped keys
        if openai_key and openai_key.startswith("gsk_"):
            groq_key = openai_key
            openai_key = None
        if groq_key and groq_key.startswith("sk-"):
            openai_key = groq_key
            groq_key = None

        provider = (settings.LLM_PROVIDER or "").lower().strip()
        model = settings.LLM_MODEL or ""

        # Auto-resolve provider based on available keys & model name
        if groq_key and not openai_key:
            provider = "groq"
        elif openai_key and not groq_key and provider != "ollama":
            provider = "openai"
        elif not groq_key and not openai_key and provider in ["groq", "openai"]:
            provider = "ollama"

        if provider == "groq" or (groq_key and "llama" in model.lower()):
            from langchain_groq import ChatGroq
            # Fallback to standard Groq model if model is OpenAI-like or invalid
            if "gpt" in model.lower() or not model:
                model = "llama-3.1-8b-instant"
            logger.info(f"Using Cloud Groq LLM: {model}")
            client = ChatGroq(
                model=model,
                api_key=groq_key,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            return client, model, "groq"

        elif provider == "openai" or (openai_key and ("gpt" in model.lower() or not groq_key)):
            from langchain_openai import ChatOpenAI
            if "llama" in model.lower() or "mixtral" in model.lower() or not model:
                model = "gpt-4o-mini"
            logger.info(f"Using Cloud OpenAI LLM: {model}")
            client = ChatOpenAI(
                model=model,
                api_key=openai_key,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            return client, model, "openai"

        else:
            logger.info(f"Using Local Ollama LLM: {model or 'llama3.2'}")
            client = ChatOllama(
                model=model or "llama3.2",
                base_url=settings.OLLAMA_BASE_URL,
                temperature=settings.LLM_TEMPERATURE,
                num_predict=settings.LLM_MAX_TOKENS,
            )
            return client, model or "llama3.2", "ollama"

    def _invoke_llm_with_fallback(self, messages) -> str:
        """Invokes LLM with automatic model fallback in case of 404 or transient errors."""
        try:
            resp = self.llm.invoke(messages)
            return resp.content
        except Exception as e:
            err_str = str(e).lower()
            logger.warning(f"Primary LLM invocation failed: {e}")

            groq_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
            if groq_key and ("404" in err_str or "model_not_found" in err_str or "does not exist" in err_str or "invalid_request_error" in err_str):
                fallback_models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"]
                for fb in fallback_models:
                    if fb == self.model_name:
                        continue
                    try:
                        logger.info(f"Attempting self-healing fallback to Groq model: {fb}")
                        from langchain_groq import ChatGroq
                        fallback_llm = ChatGroq(
                            model=fb,
                            api_key=groq_key,
                            temperature=settings.LLM_TEMPERATURE,
                            max_tokens=settings.LLM_MAX_TOKENS,
                        )
                        resp = fallback_llm.invoke(messages)
                        self.llm = fallback_llm
                        self.model_name = fb
                        logger.success(f"Self-healing fallback succeeded with {fb}")
                        return resp.content
                    except Exception as fb_err:
                        logger.warning(f"Fallback model {fb} failed: {fb_err}")
                        continue

            openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
            if openai_key and ("404" in err_str or "model_not_found" in err_str or "does not exist" in err_str):
                try:
                    logger.info("Attempting self-healing fallback to OpenAI model: gpt-4o-mini")
                    from langchain_openai import ChatOpenAI
                    fallback_llm = ChatOpenAI(
                        model="gpt-4o-mini",
                        api_key=openai_key,
                        temperature=settings.LLM_TEMPERATURE,
                        max_tokens=settings.LLM_MAX_TOKENS,
                    )
                    resp = fallback_llm.invoke(messages)
                    self.llm = fallback_llm
                    self.model_name = "gpt-4o-mini"
                    return resp.content
                except Exception as fb_err:
                    logger.warning(f"OpenAI fallback failed: {fb_err}")

            if "connection refused" in err_str or "11434" in err_str or "failed to connect" in err_str:
                return (
                    "Hello! I am Loca. The backend is currently running in cloud mode, but Ollama is not accessible on localhost. "
                    "Please provide a GROQ_API_KEY or OPENAI_API_KEY in the backend environment variables to enable cloud generation."
                )

            # Re-raise if completely unhandled
            raise e

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
        if docs and getattr(settings, "USE_RERANKER", False):
            try:
                docs = self.vs.rerank(question, docs, top_k=settings.RETRIEVAL_TOP_K)
                logger.info(f"Re-ranked to {len(docs)} chunks")
            except Exception as e:
                logger.warning(f"Re-ranking failed or skipped: {e}")

        # Step 3: Call LLM with or without context
        messages = []
        if docs:
            context = format_context(docs)
            user_message = f"Context:\n{context}\n\nQuestion: {question}"
            messages.append(SystemMessage(content=SYSTEM_PROMPT))
        else:
            user_message = question
            messages.append(SystemMessage(content=NO_CONTEXT_PROMPT))

        # Add conversation history if available
        if chat_history:
            for msg in chat_history[-settings.MEMORY_WINDOW:]:
                if msg.get("role") == "user":
                    messages.append(HumanMessage(content=msg.get("content", "")))
                elif msg.get("role") == "assistant":
                    messages.append(AIMessage(content=msg.get("content", "")))

        messages.append(HumanMessage(content=user_message))

        # Step 4: Resilient LLM call
        answer = self._invoke_llm_with_fallback(messages)

        logger.success(f"Generated answer ({len(answer)} chars)")
        return {
            "answer": answer,
            "sources": docs,
            "num_sources": len(docs),
        }

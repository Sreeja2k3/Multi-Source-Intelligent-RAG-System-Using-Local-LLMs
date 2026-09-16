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
        self.llm, self.model_name, self.provider, self.groq_key, self.openai_key = self._resolve_llm_client()

    def _resolve_llm_client(self):
        """Auto-detects keys, fixes provider mismatches, and instantiates the proper LLM."""
        raw_groq = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_KEY") or os.environ.get("GROQ_API")
        raw_openai = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_KEY") or os.environ.get("OPENAI_API")

        groq_key = None
        openai_key = None

        for k in [raw_groq, raw_openai]:
            if k and isinstance(k, str) and k.strip():
                k_clean = k.strip()
                if k_clean.startswith("gsk_"):
                    groq_key = k_clean
                elif k_clean.startswith("sk-"):
                    openai_key = k_clean

        if not groq_key and not openai_key:
            if raw_groq and str(raw_groq).strip():
                groq_key = str(raw_groq).strip()
            elif raw_openai and str(raw_openai).strip():
                openai_key = str(raw_openai).strip()

        # Route strictly based on identified key
        if groq_key:
            provider = "groq"
        elif openai_key:
            provider = "openai"
        else:
            provider = (settings.LLM_PROVIDER or "ollama").lower().strip()

        if provider == "groq" and groq_key:
            model = settings.LLM_MODEL or "llama-3.3-70b-versatile"
            if "gpt" in model.lower() or not model or model == "llama3.2":
                model = "llama-3.3-70b-versatile"
            logger.info(f"Using Cloud Groq LLM: {model}")
            from langchain_groq import ChatGroq
            client = ChatGroq(
                model=model,
                api_key=groq_key,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            return client, model, "groq", groq_key, None

        elif provider == "openai" and openai_key:
            model = "gpt-4o-mini"
            logger.info(f"Using Cloud OpenAI LLM: {model}")
            from langchain_openai import ChatOpenAI
            client = ChatOpenAI(
                model=model,
                api_key=openai_key,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            return client, model, "openai", None, openai_key

        else:
            model = settings.LLM_MODEL or "llama3.2"
            logger.info(f"Using Local Ollama LLM: {model}")
            client = ChatOllama(
                model=model,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=settings.LLM_TEMPERATURE,
                num_predict=settings.LLM_MAX_TOKENS,
            )
            return client, model, "ollama", None, None

    def _invoke_llm_with_fallback(self, messages) -> str:
        """Invokes LLM with automatic model fallback and dynamic key re-resolution."""
        # Check if new keys have been added to environment since startup
        curr_groq = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
        curr_openai = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
        if (curr_groq and not self.groq_key) or (curr_openai and not self.openai_key):
            logger.info("Detected newly configured API key in environment, re-initializing LLM client...")
            self.llm, self.model_name, self.provider, self.groq_key, self.openai_key = self._resolve_llm_client()

        try:
            resp = self.llm.invoke(messages)
            return resp.content
        except Exception as e:
            err_str = str(e).lower()
            logger.warning(f"Primary LLM invocation ({self.model_name}) failed: {e}")

            groq_k = self.groq_key or curr_groq
            if groq_k:
                fallback_models = [
                    "llama-3.3-70b-versatile",
                    "llama3-70b-8192",
                    "llama3-8b-8192",
                    "llama-3.1-8b-instant",
                    "mixtral-8x7b-32768",
                    "gemma2-9b-it",
                ]
                for fb in fallback_models:
                    if fb == self.model_name:
                        continue
                    try:
                        logger.info(f"Attempting self-healing fallback to Groq model: {fb}")
                        from langchain_groq import ChatGroq
                        fallback_llm = ChatGroq(
                            model=fb,
                            api_key=groq_k,
                            temperature=settings.LLM_TEMPERATURE,
                            max_tokens=settings.LLM_MAX_TOKENS,
                        )
                        resp = fallback_llm.invoke(messages)
                        self.llm = fallback_llm
                        self.model_name = fb
                        self.groq_key = groq_k
                        logger.success(f"Self-healing fallback succeeded with {fb}")
                        return resp.content
                    except Exception as fb_err:
                        logger.warning(f"Fallback model {fb} failed: {fb_err}")
                        continue

            openai_k = self.openai_key or curr_openai
            if openai_k:
                fallback_models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
                for fb in fallback_models:
                    if fb == self.model_name:
                        continue
                    try:
                        logger.info(f"Attempting self-healing fallback to OpenAI model: {fb}")
                        from langchain_openai import ChatOpenAI
                        fallback_llm = ChatOpenAI(
                            model=fb,
                            api_key=openai_k,
                            temperature=settings.LLM_TEMPERATURE,
                            max_tokens=settings.LLM_MAX_TOKENS,
                        )
                        resp = fallback_llm.invoke(messages)
                        self.llm = fallback_llm
                        self.model_name = fb
                        self.openai_key = openai_k
                        logger.success(f"Self-healing OpenAI fallback succeeded with {fb}")
                        return resp.content
                    except Exception as fb_err:
                        logger.warning(f"OpenAI fallback {fb} failed: {fb_err}")
                        continue

            if "connection refused" in err_str or "11434" in err_str or "failed to connect" in err_str:
                return (
                    "Hello! I am Loca. The backend is running in cloud mode, but Ollama is not accessible on localhost. "
                    "Please set GROQ_API_KEY in Render's Environment settings to enable free cloud generation."
                )

            if "invalid_api_key" in err_str or "incorrect api key" in err_str or "authentication" in err_str or "401" in err_str or "403" in err_str:
                return "The configured API key was rejected by the provider. Please verify your GROQ_API_KEY in Render."

            return f"I received your question, but encountered an API response error from the provider ({e}). Please verify that your API key is active."

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

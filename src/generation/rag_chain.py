import os
import re
from typing import List, Optional
from loguru import logger
from langchain_core.documents import Document
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from src.config import settings
from src.retrieval.vector_store import VectorStoreManager


SYSTEM_PROMPT = """You are Loca, an intelligent, accurate, and concise private AI assistant.
Answer the user's question using ONLY the provided context from their indexed documents, files, and links.

Strict Accuracy Rules:
1. Grounding: Rely strictly on facts directly mentioned in the provided context. Do NOT invent, assume, or extrapolate facts.
2. Direct Answer: Answer what the user specifically asked.
   - If the user asks about a specific person, entity, skill, or topic (e.g. "who is [Name]" or "what is [Topic]") and that person/topic is NOT described in the context, clearly state:
     "I could not find information about [Name/Topic] in the currently indexed documents."
   - Do NOT substitute or output a summary of an unrelated document or video when asked about something else.
3. Relevant Summaries: Only provide a summary of a document, video, or URL if the user explicitly asks for a summary or overview.
4. Source Attribution: When answering from the context, mention the relevant source document name (e.g., [Source: filename]).
5. Conciseness & Structure: Keep answers direct, well-structured (using bullet points where appropriate), and free of unnecessary fluff."""

NO_CONTEXT_PROMPT = """You are Loca, a helpful and friendly private AI assistant. 
The user has not indexed or uploaded any documents to their knowledge base yet, so you do not have specific document context.
Answer their greeting or question generally using your own knowledge. 
Remind them gently that if they want to query specific documents (PDF, DOCX, TXT, CSV, JSON, Web URLs, or YouTube videos), they can upload them in the "Knowledge Base" tab."""


def format_context(docs: List[Document]) -> str:
    """Format retrieved docs into a context string for the prompt with source labels."""
    parts = []
    for doc in docs:
        source = doc.metadata.get("url") or doc.metadata.get("file_name") or doc.metadata.get("title") or "Document"
        parts.append(f"[Source: {source}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def is_referential_followup(question: str) -> bool:
    """Returns True if the question is an anaphoric follow-up referencing prior context."""
    q = question.strip().lower()
    words = set(re.findall(r'\b[a-z0-9_]+\b', q))

    # Standalone entity or direct factual questions should NEVER be treated as follow-up
    # e.g. "who is Vangara Sreeja", "what is machine learning", "where was ..."
    if re.match(r'^(who|whom|whose)\s+(is|was|are|were)\b', q):
        return False
    if re.match(r'^(what|where|when|why|how)\s+(is|was|are|were)\s+([a-z0-9_-]+\s+){1,}[a-z0-9_-]+', q) and not any(w in words for w in ("it", "this", "that", "these", "those")):
        return False

    # Check for explicit referential phrases pointing to prior context
    referential_phrases = [
        "the url", "the video", "the link", "the document", "the file", "the paper",
        "tell me more", "explain more", "summarize it", "summarize this", "what about it", "what else",
        "elaborate", "continue", "give me more"
    ]
    if any(p in q for p in referential_phrases):
        return True

    # Check for referential pronouns
    referential_pronouns = {"it", "this", "that", "these", "those", "they", "them", "earlier", "above"}
    if words & referential_pronouns:
        return True

    return False


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
            model = settings.LLM_MODEL
            # Fast, low-latency 20B model on Groq is default when unconfigured or using local name
            if not model or model in ("llama3.2", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"):
                model = "openai/gpt-oss-20b"
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
                    "openai/gpt-oss-20b",
                    "openai/gpt-oss-120b",
                    "qwen/qwen3.6-27b",
                    "qwen/qwen3-32b",
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

    def query(
        self,
        question: str,
        chat_history: Optional[List[dict]] = None,
        source_filter: Optional[str] = None,
    ) -> dict:
        # Step 1: Retrieve relevant chunks
        try:
            search_query = question.strip()
            # Only enrich query if the question is an explicit referential/follow-up question
            # Standalone entity queries (e.g. "who is Vangara Sreeja") must NEVER be polluted with past messages
            if chat_history and is_referential_followup(question):
                past_user_msgs = [m["content"] for m in chat_history if m.get("role") == "user" and m.get("content")]
                if past_user_msgs:
                    search_query = f"{past_user_msgs[-1]} {question}"

            # Apply metadata filter if specific source requested
            filter_dict = None
            if source_filter and source_filter != "All Sources":
                filter_dict = {"file_name": source_filter}

            if filter_dict:
                retriever = self.vs.get_retriever(filter_dict=filter_dict)
                docs = retriever.invoke(search_query)
                # Fallback if document metadata recorded under "url"
                if not docs and (source_filter.startswith("http://") or source_filter.startswith("https://")):
                    try:
                        retriever_url = self.vs.get_retriever(filter_dict={"url": source_filter})
                        docs = retriever_url.invoke(search_query)
                    except Exception:
                        pass
            else:
                retriever = self.vs.get_retriever()
                docs = retriever.invoke(search_query)

            # If no docs found with enriched query, try raw question
            if not docs and search_query != question:
                retriever_raw = self.vs.get_retriever(filter_dict=filter_dict) if filter_dict else self.vs.get_retriever()
                docs = retriever_raw.invoke(question)

            logger.info(f"Retrieved {len(docs)} chunks for query: '{search_query}' (source_filter: {source_filter})")
        except Exception as e:
            logger.warning(f"Retrieval skipped or failed (likely empty vector database): {e}")
            docs = []

        # Step 2: Re-rank chunks using cross-encoder for better relevance (if enabled)
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

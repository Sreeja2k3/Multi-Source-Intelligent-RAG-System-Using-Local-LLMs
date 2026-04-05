# ui/app.py
# Streamlit UI — calls the FastAPI backend over HTTP.
# Run with: streamlit run ui/app.py
# Requires API running: uvicorn api:app --reload --port 8000

import streamlit as st
import requests
from pathlib import Path

API_URL = "http://localhost:8000"

st.set_page_config(page_title="RAG System", page_icon="🧠", layout="wide")

# ── Helper functions ──────────────────────────────────────────────────────────
def get_stats():
    try:
        return requests.get(f"{API_URL}/stats", timeout=5).json()
    except:
        return {"total_chunks": 0, "collection": "unknown"}

def get_sources():
    try:
        return requests.get(f"{API_URL}/sources", timeout=5).json().get("sources", [])
    except:
        return []

def query_api(question, chat_history=None, source_filter=None):
    payload = {"question": question}
    if chat_history:
        payload["chat_history"] = chat_history
    if source_filter and source_filter != "All Sources":
        payload["source_filter"] = source_filter
    r = requests.post(f"{API_URL}/query", json=payload, timeout=120)
    r.raise_for_status()
    return r.json()

def ingest_url_api(url):
    r = requests.post(f"{API_URL}/ingest/url", json={"url": url}, timeout=30)
    r.raise_for_status()
    return r.json()

def ingest_file_api(file_bytes, filename):
    r = requests.post(f"{API_URL}/ingest/file", files={"file": (filename, file_bytes)}, timeout=60)
    r.raise_for_status()
    return r.json()

def ingest_youtube_api(url):
    r = requests.post(f"{API_URL}/ingest/youtube", json={"url": url}, timeout=30)
    r.raise_for_status()
    return r.json()

def check_health():
    try:
        return requests.get(f"{API_URL}/health", timeout=3).status_code == 200
    except:
        return False

# ── Session state ─────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# ── Check API is running ──────────────────────────────────────────────────────
if not check_health():
    st.error("API is not running. Start it with: `uvicorn api:app --reload --port 8000`")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📥 Add Sources")
    stats = get_stats()
    st.metric("Chunks Indexed", stats["total_chunks"])
    st.caption(f"API: {API_URL}")
    st.divider()

    # Source filter dropdown
    sources = get_sources()
    source_options = ["All Sources"] + sources
    selected_source = st.selectbox("Filter by source", source_options)
    st.divider()

    # Clear chat button
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.history = []
        st.rerun()

    st.divider()

    st.subheader("Upload File")
    uploaded = st.file_uploader("PDF, DOCX, TXT, CSV, or JSON", type=["pdf", "docx", "txt", "csv", "json"])
    if uploaded and st.button("Index File", use_container_width=True):
        try:
            with st.spinner(f"Indexing {uploaded.name}..."):
                result = ingest_file_api(uploaded.read(), uploaded.name)
            st.success(f"Indexed {result['chunks_indexed']} chunks")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()

    st.subheader("Web URL")
    url = st.text_input("URL", placeholder="https://en.wikipedia.org/wiki/...")
    if st.button("Index URL", use_container_width=True) and url:
        try:
            with st.spinner("Scraping URL..."):
                result = ingest_url_api(url)
            st.success(f"Indexed {result['chunks_indexed']} chunks")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()

    st.subheader("YouTube")
    yt_url = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...")
    if st.button("Index Video", use_container_width=True) and yt_url:
        try:
            with st.spinner("Fetching transcript..."):
                result = ingest_youtube_api(yt_url)
            st.success(f"Indexed {result['chunks_indexed']} chunks")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# ── Main chat ─────────────────────────────────────────────────────────────────
st.title("🧠 Multi-Source RAG System")
st.caption("Powered by FastAPI + Ollama (local LLM) | Conversation memory enabled")

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"📚 {len(msg['sources'])} source chunks used"):
                for i, src in enumerate(msg["sources"], 1):
                    st.markdown(f"**[{i}]** `{src.get('source_type','?')}` — "
                                f"{src.get('file_name') or src.get('url', '')}")
                    st.divider()

question = st.chat_input("Ask something about your documents...")
if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if stats["total_chunks"] == 0:
            st.warning("No documents indexed yet. Use the sidebar to add sources.")
        else:
            # Build chat history for conversation memory
            chat_history = []
            for msg in st.session_state.history[:-1]:  # exclude current question
                if msg["role"] in ("user", "assistant"):
                    chat_history.append({"role": msg["role"], "content": msg["content"]})

            with st.spinner("Thinking..."):
                try:
                    result = query_api(
                        question,
                        chat_history=chat_history if chat_history else None,
                        source_filter=selected_source,
                    )
                except requests.exceptions.Timeout:
                    st.error("Request timed out. Try again.")
                    st.stop()
                except Exception as e:
                    st.error(f"API error: {e}")
                    st.stop()

            st.markdown(result["answer"])

            if result.get("sources"):
                with st.expander(f"📚 {result['num_sources']} source chunks used"):
                    for i, src in enumerate(result["sources"], 1):
                        st.markdown(f"**[{i}]** `{src.get('source_type','?')}` — "
                                    f"{src.get('file_name') or src.get('url', '')}")
                        st.divider()

            st.session_state.history.append({
                "role": "assistant",
                "content": result["answer"],
                "sources": result.get("sources", []),
            })

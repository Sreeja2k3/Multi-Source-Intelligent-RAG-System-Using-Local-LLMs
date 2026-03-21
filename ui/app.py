# ui/app.py
# Run with: streamlit run ui/app.py  (from the rag_v2/ root directory)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tempfile
from pathlib import Path
import streamlit as st

from src.retrieval.vector_store import VectorStoreManager
from src.ingestion.pipeline import IngestionPipeline
from src.generation.rag_chain import RAGChain

st.set_page_config(page_title="RAG System", page_icon="🧠", layout="wide")

# ── Session state — persists across Streamlit reruns ─────────────────────────
if "vs" not in st.session_state:
    vs = VectorStoreManager().create_or_load()
    st.session_state.vs = vs
    st.session_state.pipeline = IngestionPipeline(vs)
    st.session_state.rag = RAGChain(vs)
    st.session_state.history = []

vs = st.session_state.vs
pipeline = st.session_state.pipeline
rag = st.session_state.rag

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📥 Add Sources")
    stats = vs.get_collection_stats()
    st.metric("Chunks Indexed", stats["total_chunks"])
    st.divider()

    # File upload
    st.subheader("Upload File")
    uploaded = st.file_uploader("PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    if uploaded and st.button("Index File", use_container_width=True):
        suffix = Path(uploaded.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name
        try:
            with st.spinner(f"Indexing {uploaded.name}..."):
                if suffix == ".pdf":
                    n = pipeline.ingest_pdf(tmp_path)
                elif suffix == ".docx":
                    n = pipeline.ingest_docx(tmp_path)
                else:
                    n = pipeline.ingest_txt(tmp_path)
            st.success(f"Indexed {n} chunks")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")
        finally:
            os.unlink(tmp_path)

    st.divider()

    # URL
    st.subheader("Web URL")
    url = st.text_input("URL", placeholder="https://en.wikipedia.org/wiki/...")
    if st.button("Index URL", use_container_width=True) and url:
        try:
            with st.spinner("Scraping URL..."):
                n = pipeline.ingest_url(url)
            st.success(f"Indexed {n} chunks")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()

    # YouTube
    st.subheader("YouTube")
    yt_url = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...")
    if st.button("Index Video", use_container_width=True) and yt_url:
        try:
            with st.spinner("Fetching transcript..."):
                n = pipeline.ingest_youtube(yt_url)
            st.success(f"Indexed {n} chunks")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# ── Main chat ─────────────────────────────────────────────────────────────────
st.title("🧠 Multi-Source RAG System")
st.caption("Ask questions about your indexed documents")

# Show chat history
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander(f"📚 {len(msg['sources'])} source chunks used"):
                for i, doc in enumerate(msg["sources"], 1):
                    meta = doc.metadata
                    st.markdown(f"**[{i}]** `{meta.get('source_type','?')}` — "
                                f"{meta.get('file_name', meta.get('url', ''))}")
                    preview = doc.page_content[:300]
                    st.text(preview + ("..." if len(doc.page_content) > 300 else ""))
                    st.divider()

# Chat input
question = st.chat_input("Ask something about your documents...")
if question:
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if stats["total_chunks"] == 0:
            st.warning("No documents indexed yet. Use the sidebar to add sources.")
        else:
            with st.spinner("Retrieving and generating..."):
                result = rag.query(question)

            st.markdown(result["answer"])

            if result["sources"]:
                with st.expander(f"📚 {result['num_sources']} source chunks used"):
                    for i, doc in enumerate(result["sources"], 1):
                        meta = doc.metadata
                        st.markdown(f"**[{i}]** `{meta.get('source_type','?')}` — "
                                    f"{meta.get('file_name', meta.get('url', ''))}")
                        preview = doc.page_content[:300]
                        st.text(preview + ("..." if len(doc.page_content) > 300 else ""))
                        st.divider()

            st.session_state.history.append({
                "role": "assistant",
                "content": result["answer"],
                "sources": result["sources"],
            })

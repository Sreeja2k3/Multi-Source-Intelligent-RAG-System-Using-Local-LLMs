# ui/pages/knowledge.py — Knowledge Base Management

import time
import streamlit as st
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (
    apply_theme, init_state, check_health, page_header, metric_card,
    get_stats, get_sources,
    ingest_file_api, ingest_url_api, ingest_youtube_api,
    delete_source_api, clear_index_api,
    API_URL,
)

apply_theme()
init_state()

if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False
if "confirm_delete_src" not in st.session_state:
    st.session_state.confirm_delete_src = None

# ── Prefetch data ────────────────────────────────────────────────────────────
api_ok = check_health()
stats = get_stats() if api_ok else {"total_chunks": 0, "collection": "?"}
sources = get_sources() if api_ok else []

if not api_ok:
    st.error("\u26a0\ufe0f **API is offline.** Start the backend first:")
    st.code("uvicorn api:app --reload --port 8000", language="bash")
    st.stop()

page_header("\U0001f4da", "Knowledge Base", "Manage your document sources")


# ── Stats Row ────────────────────────────────────────────────────────────────

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(metric_card(stats["total_chunks"], "Total Chunks"), unsafe_allow_html=True)
with c2:
    st.markdown(metric_card(len(sources), "Sources Indexed"), unsafe_allow_html=True)
with c3:
    st.markdown(metric_card(stats.get("collection", "rag_collection"), "Collection"), unsafe_allow_html=True)

st.markdown("")


# ── Ingestion Section ────────────────────────────────────────────────────────

st.markdown("### \u2795 Add New Sources")

col_file, col_url, col_yt = st.columns(3)

with col_file:
    st.markdown("""
    <div class="ingest-card">
        <div class="icon">\U0001f4c1</div>
        <h4>Upload File</h4>
        <p>PDF, DOCX, TXT, CSV, JSON</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Choose file",
        type=["pdf", "docx", "txt", "csv", "json"],
        label_visibility="collapsed",
        key="kb_upload",
    )
    if uploaded and st.button("\U0001f4e4 Index File", key="kb_idx_file", use_container_width=True):
        try:
            with st.status(f"Indexing {uploaded.name}...", expanded=True) as status:
                st.write("\U0001f4c4 Reading document...")
                file_bytes = uploaded.read()
                st.write("\u2702\ufe0f Chunking text...")
                st.write("\U0001f9e0 Generating embeddings...")
                result = ingest_file_api(file_bytes, uploaded.name)
                st.write("\U0001f4be Stored in vector database")
                status.update(label=f"\u2713 Indexed {result['chunks_indexed']} chunks from {uploaded.name}", state="complete")
            st.rerun()
        except Exception as e:
            st.error(f"\u274c {e}")

with col_url:
    st.markdown("""
    <div class="ingest-card">
        <div class="icon">\U0001f310</div>
        <h4>Web Page</h4>
        <p>Any public URL</p>
    </div>
    """, unsafe_allow_html=True)

    url_input = st.text_input("URL", placeholder="https://...", label_visibility="collapsed", key="kb_url")
    if st.button("\U0001f310 Index URL", key="kb_idx_url", use_container_width=True) and url_input:
        try:
            with st.status("Indexing web page...", expanded=True) as status:
                st.write("\U0001f310 Fetching page content...")
                st.write("\U0001f9f9 Cleaning HTML & extracting text...")
                st.write("\u2702\ufe0f Chunking & embedding...")
                result = ingest_url_api(url_input)
                status.update(label=f"\u2713 Indexed {result['chunks_indexed']} chunks from URL", state="complete")
            st.rerun()
        except Exception as e:
            st.error(f"\u274c {e}")

with col_yt:
    st.markdown("""
    <div class="ingest-card">
        <div class="icon">\U0001f3ac</div>
        <h4>YouTube Video</h4>
        <p>Fetches transcript automatically</p>
    </div>
    """, unsafe_allow_html=True)

    yt_input = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed", key="kb_yt")
    if st.button("\U0001f3ac Index Video", key="kb_idx_yt", use_container_width=True) and yt_input:
        try:
            with st.status("Indexing YouTube video...", expanded=True) as status:
                st.write("\U0001f3ac Fetching video transcript...")
                st.write("\U0001f4dd Processing transcript text...")
                st.write("\u2702\ufe0f Chunking & embedding...")
                result = ingest_youtube_api(yt_input)
                status.update(label=f"\u2713 Indexed {result['chunks_indexed']} chunks from YouTube", state="complete")
            st.rerun()
        except Exception as e:
            st.error(f"\u274c {e}")


# ── Indexed Sources ──────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### \U0001f4c2 Indexed Sources")

if sources:
    for src_name in sources:
        col_name, col_del = st.columns([5, 1])
        with col_name:
            if src_name.endswith(".pdf"):
                icon = "\U0001f4c4"
            elif src_name.endswith(".docx"):
                icon = "\U0001f4dd"
            elif src_name.endswith(".txt"):
                icon = "\U0001f4c3"
            elif src_name.endswith(".csv"):
                icon = "\U0001f4ca"
            elif src_name.endswith(".json"):
                icon = "\U0001f4cb"
            elif src_name.startswith("http"):
                icon = "\U0001f310"
            else:
                icon = "\U0001f4c1"
            st.markdown(f"{icon} **{src_name}**")

        with col_del:
            if st.session_state.confirm_delete_src == src_name:
                c_yes, c_no = st.columns(2)
                with c_yes:
                    if st.button("\u2713", key=f"yes_{src_name}"):
                        try:
                            with st.spinner("\U0001f5d1 Removing..."):
                                result = delete_source_api(src_name)
                            st.toast(f"Deleted {result['chunks_indexed']} chunks", icon="\u2713")
                            st.session_state.confirm_delete_src = None
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with c_no:
                    if st.button("\u2717", key=f"no_{src_name}"):
                        st.session_state.confirm_delete_src = None
                        st.rerun()
            else:
                st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                if st.button("\U0001f5d1", key=f"del_{src_name}"):
                    st.session_state.confirm_delete_src = src_name
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<hr style="margin:0.2rem 0; border-color:#1e1e2e;">', unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="text-align:center; padding:2rem; color:#666;">
        <div style="font-size:2rem; margin-bottom:0.5rem;">\U0001f4ed</div>
        <p>No sources indexed yet. Use the options above to add documents.</p>
    </div>
    """, unsafe_allow_html=True)


# ── Danger Zone ──────────────────────────────────────────────────────────────

if sources:
    st.markdown("")
    st.markdown("""
    <div class="danger-zone">
        <h4>\u26a0\ufe0f Danger Zone</h4>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.confirm_clear:
        st.error("**This will permanently delete ALL indexed documents.** Are you sure?")
        c1, c2, c3 = st.columns([1, 1, 3])
        with c1:
            if st.button("\u2713 Yes, clear all", key="confirm_clear_yes", type="primary"):
                try:
                    with st.spinner("\U0001f5d1 Clearing entire index..."):
                        result = clear_index_api()
                    st.toast(f"Cleared {result['chunks_indexed']} chunks", icon="\u2713")
                    st.session_state.confirm_clear = False
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        with c2:
            if st.button("\u2717 Cancel", key="confirm_clear_no"):
                st.session_state.confirm_clear = False
                st.rerun()
    else:
        if st.button("\U0001f5d1 Clear Entire Index", key="clear_all"):
            st.session_state.confirm_clear = True
            st.rerun()

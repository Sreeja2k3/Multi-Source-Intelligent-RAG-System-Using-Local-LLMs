# ui/pages/knowledge.py — Knowledge Base Management

import time
import streamlit as st
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (
    apply_theme, init_state, check_health, page_header, metric_card,
    get_stats, get_sources, page_loader, quick_loader, brand_bar,
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
if "kb_loaded" not in st.session_state:
    _pl = page_loader("\U0001f4da", "Knowledge Base", ["Checking backend...", "Loading indexed sources...", "Fetching stats..."])
    api_ok = check_health()
    stats = get_stats() if api_ok else {"total_chunks": 0, "collection": "?"}
    sources = get_sources() if api_ok else []
    _pl.empty()
    st.session_state.kb_loaded = True
else:
    _show_ql = st.session_state.get("_last_page") != "kb"
    if _show_ql:
        _ql = quick_loader("Loading Knowledge Base...")
    api_ok = check_health()
    stats = get_stats() if api_ok else {"total_chunks": 0, "collection": "?"}
    sources = get_sources() if api_ok else []
    if _show_ql:
        _ql.empty()
st.session_state._last_page = "kb"

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


# ── Add Sources ──────────────────────────────────────────────────────────────

st.markdown("")
st.markdown("### \u2795 Add New Sources")

source_type = st.radio(
    "Source type",
    ["\U0001f4c1 Upload File", "\U0001f310 Web URL", "\U0001f3ac YouTube"],
    horizontal=True,
    label_visibility="collapsed",
    key="ingest_tab",
)

if source_type == "\U0001f4c1 Upload File":
    st.caption("Supported: PDF, DOCX, TXT, CSV, JSON")
    uploaded = st.file_uploader(
        "Choose file",
        type=["pdf", "docx", "txt", "csv", "json"],
        label_visibility="collapsed",
        key="kb_upload",
    )
    if uploaded:
        if st.button(f"\U0001f4e4 Index **{uploaded.name}**", key="kb_idx_file", use_container_width=True, type="primary"):
            try:
                with st.status(f"Indexing {uploaded.name}...", expanded=True) as status:
                    st.write("\U0001f4c4 Reading document...")
                    file_bytes = uploaded.read()
                    st.write("\u2702\ufe0f Chunking text...")
                    st.write("\U0001f9e0 Generating embeddings...")
                    result = ingest_file_api(file_bytes, uploaded.name)
                    st.write("\U0001f4be Stored in vector database")
                    status.update(label=f"\u2713 Indexed {result['chunks_indexed']} chunks from {uploaded.name}", state="complete")
                get_stats.clear()
                get_sources.clear()
                st.rerun()
            except Exception as e:
                st.error(f"\u274c {e}")

elif source_type == "\U0001f310 Web URL":
    st.caption("Paste any public web page URL")
    url_input = st.text_input("URL", placeholder="https://en.wikipedia.org/wiki/...", label_visibility="collapsed", key="kb_url")
    if st.button("\U0001f310 Index URL", key="kb_idx_url", use_container_width=True, type="primary", disabled=not url_input):
        try:
            with st.status("Indexing web page...", expanded=True) as status:
                st.write("\U0001f310 Fetching page content...")
                st.write("\U0001f9f9 Cleaning HTML & extracting text...")
                st.write("\u2702\ufe0f Chunking & embedding...")
                result = ingest_url_api(url_input)
                status.update(label=f"\u2713 Indexed {result['chunks_indexed']} chunks", state="complete")
            get_stats.clear()
            get_sources.clear()
            st.rerun()
        except Exception as e:
            st.error(f"\u274c {e}")

elif source_type == "\U0001f3ac YouTube":
    st.caption("Paste a YouTube video URL (transcript will be fetched automatically)")
    yt_input = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed", key="kb_yt")
    if st.button("\U0001f3ac Index Video", key="kb_idx_yt", use_container_width=True, type="primary", disabled=not yt_input):
        try:
            with st.status("Indexing YouTube video...", expanded=True) as status:
                st.write("\U0001f3ac Fetching video transcript...")
                st.write("\U0001f4dd Processing transcript text...")
                st.write("\u2702\ufe0f Chunking & embedding...")
                result = ingest_youtube_api(yt_input)
                status.update(label=f"\u2713 Indexed {result['chunks_indexed']} chunks", state="complete")
            get_stats.clear()
            get_sources.clear()
            st.rerun()
        except Exception as e:
            st.error(f"\u274c {e}")


# ── Indexed Sources ──────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### \U0001f4c2 Indexed Sources")

if sources:
    for src_name in sources:
        # Detect source type icon
        if src_name.endswith(".pdf"):
            icon, badge = "\U0001f4c4", "PDF"
        elif src_name.endswith(".docx"):
            icon, badge = "\U0001f4dd", "DOCX"
        elif src_name.endswith(".txt"):
            icon, badge = "\U0001f4c3", "TXT"
        elif src_name.endswith(".csv"):
            icon, badge = "\U0001f4ca", "CSV"
        elif src_name.endswith(".json"):
            icon, badge = "\U0001f4cb", "JSON"
        elif "youtube.com" in src_name or "youtu.be" in src_name:
            icon, badge = "\U0001f3ac", "YouTube"
        elif src_name.startswith("http"):
            icon, badge = "\U0001f310", "WEB"
        else:
            icon, badge = "\U0001f4c1", "FILE"

        # Truncate long names
        display_name = src_name if len(src_name) <= 50 else src_name[:47] + "..."

        col_icon, col_name, col_badge, col_del = st.columns([0.5, 5, 1, 1])
        with col_icon:
            st.markdown(f"<div style='font-size:1.2rem; padding-top:0.2rem;'>{icon}</div>", unsafe_allow_html=True)
        with col_name:
            st.markdown(f"**{display_name}**")
        with col_badge:
            st.markdown(f"<span style='background:#1a365d; color:#93c5fd; padding:0.15rem 0.5rem; border-radius:10px; font-size:0.7rem; font-weight:600;'>{badge}</span>", unsafe_allow_html=True)
        with col_del:
            if st.session_state.confirm_delete_src == src_name:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("\u2713", key=f"yes_{src_name}"):
                        try:
                            with st.spinner("Removing..."):
                                result = delete_source_api(src_name)
                            st.toast(f"Deleted {result['chunks_indexed']} chunks", icon="\u2713")
                            st.session_state.confirm_delete_src = None
                            get_stats.clear()
                            get_sources.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with c2:
                    if st.button("\u2717", key=f"no_{src_name}"):
                        st.session_state.confirm_delete_src = None
                        st.rerun()
            else:
                if st.button("\U0001f5d1", key=f"del_{src_name}"):
                    st.session_state.confirm_delete_src = src_name
                    st.rerun()
else:
    st.markdown("""
    <div style="text-align:center; padding:2rem; color:#666;">
        <div style="font-size:2rem; margin-bottom:0.5rem;">\U0001f4ed</div>
        <p>No sources indexed yet. Use the tabs above to add documents.</p>
    </div>
    """, unsafe_allow_html=True)


# ── Danger Zone ──────────────────────────────────────────────────────────────

if sources:
    st.markdown("---")

    with st.expander("\u26a0\ufe0f Danger Zone", expanded=False):
        st.caption("Permanently delete all indexed documents from the vector database.")

        if st.session_state.confirm_clear:
            st.error("**Are you sure?** This cannot be undone.")
            c1, c2, c3 = st.columns([1, 1, 3])
            with c1:
                if st.button("\u2713 Yes, clear all", key="confirm_clear_yes", type="primary"):
                    try:
                        with st.spinner("\U0001f5d1 Clearing..."):
                            result = clear_index_api()
                        st.toast(f"Cleared {result['chunks_indexed']} chunks", icon="\u2713")
                        st.session_state.confirm_clear = False
                        get_stats.clear()
                        get_sources.clear()
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

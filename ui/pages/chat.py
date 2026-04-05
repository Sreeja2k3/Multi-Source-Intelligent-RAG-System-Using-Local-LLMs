# ui/pages/chat.py — Clean Chat Interface

import time
import streamlit as st
import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (
    apply_theme, init_state, check_health,
    get_current_messages, add_message, save_history,
    new_conversation, delete_conversation,
    query_api, get_sources, get_stats,
    show_loader, stream_response,
    APP_NAME, APP_EMOJI,
)

apply_theme()
init_state()

# ── Startup Timeline Loader (first visit only) ──────────────────────────────
if "app_ready" not in st.session_state:

    TIMELINE_CSS = """
    <style>
    .tl-wrap {
        max-width: 420px;
        margin: 0 auto;
        padding: 1rem 0;
        font-family: 'Inter', -apple-system, sans-serif;
    }
    .tl-brand {
        text-align: center;
        margin-bottom: 2rem;
    }
    .tl-brand .logo { font-size: 3rem; }
    .tl-brand .name { font-size: 1.8rem; font-weight: 700; margin: 0.2rem 0; }
    .tl-brand .tag { font-size: 0.8rem; color: #666; }

    .tl-steps { position: relative; padding-left: 32px; }

    .tl-step {
        position: relative;
        padding-bottom: 1.4rem;
        padding-left: 18px;
    }
    .tl-step:last-child { padding-bottom: 0; }

    /* vertical line */
    .tl-step::before {
        content: '';
        position: absolute;
        left: -26px;
        top: 8px;
        bottom: -8px;
        width: 2px;
        background: #2a2a4a;
    }
    .tl-step:last-child::before { display: none; }
    .tl-step.done::before { background: #22c55e; }

    /* dot */
    .tl-step::after {
        content: '';
        position: absolute;
        left: -32px;
        top: 4px;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #2a2a4a;
        border: 2px solid #2a2a4a;
    }
    .tl-step.done::after {
        background: #22c55e;
        border-color: #22c55e;
    }
    .tl-step.active::after {
        background: transparent;
        border-color: #60a5fa;
        box-shadow: 0 0 0 3px rgba(96,165,250,0.25);
        animation: tl-pulse 1.5s ease-in-out infinite;
    }
    .tl-step.pending::after {
        background: #1a1a2e;
        border-color: #333;
    }

    @keyframes tl-pulse {
        0%, 100% { box-shadow: 0 0 0 3px rgba(96,165,250,0.15); }
        50% { box-shadow: 0 0 0 6px rgba(96,165,250,0.3); }
    }

    .tl-label {
        font-size: 0.88rem;
        font-weight: 500;
        color: #555;
    }
    .tl-step.done .tl-label { color: #4ade80; }
    .tl-step.active .tl-label { color: #93c5fd; }

    .tl-sub {
        font-size: 0.75rem;
        color: #444;
        margin-top: 0.15rem;
    }
    .tl-step.done .tl-sub { color: #555; }

    .tl-check {
        color: #22c55e;
        font-weight: 600;
        margin-right: 0.3rem;
    }

    .tl-footer {
        text-align: center;
        margin-top: 1.5rem;
        font-size: 0.85rem;
        color: #4ade80;
        font-weight: 600;
    }
    </style>
    """

    def timeline_html(steps, footer=""):
        steps_html = ""
        for state, label, sub in steps:
            check = '<span class="tl-check">\u2713</span>' if state == "done" else ""
            sub_html = f'<div class="tl-sub">{sub}</div>' if sub else ""
            steps_html += f'<div class="tl-step {state}"><div class="tl-label">{check}{label}</div>{sub_html}</div>'
        footer_html = f'<div class="tl-footer">{footer}</div>' if footer else ""
        return f'<div class="tl-wrap"><div class="tl-brand"><div class="logo">\U0001f999</div><div class="name">Loca</div><div class="tag">Your private, local AI assistant</div></div><div class="tl-steps">{steps_html}</div>{footer_html}</div>'

    # Inject CSS once (separate from HTML)
    st.markdown(TIMELINE_CSS, unsafe_allow_html=True)

    _loader = st.empty()

    # Stage 1: Initializing
    _loader.markdown(timeline_html([
        ("active", "Initializing interface", "Setting up components..."),
        ("pending", "Connect to backend", ""),
        ("pending", "Load indexed data", ""),
        ("pending", "Verify models", ""),
    ]), unsafe_allow_html=True)
    time.sleep(1.0)

    # Stage 2: Interface done
    _loader.markdown(timeline_html([
        ("done", "Interface ready", "All components loaded"),
        ("active", "Connecting to backend", "Reaching localhost:8000..."),
        ("pending", "Load indexed data", ""),
        ("pending", "Verify models", ""),
    ]), unsafe_allow_html=True)

    api_ok = check_health()
    time.sleep(0.4)

    if api_ok:
        # Stage 3: Backend connected
        _loader.markdown(timeline_html([
            ("done", "Interface ready", "All components loaded"),
            ("done", "Backend connected", "FastAPI running on port 8000"),
            ("active", "Loading indexed data", "Reading from ChromaDB..."),
            ("pending", "Verify models", ""),
        ]), unsafe_allow_html=True)

        _stats = get_stats()
        _sources = get_sources()
        time.sleep(0.5)

        # Stage 4: Data loaded
        _loader.markdown(timeline_html([
            ("done", "Interface ready", "All components loaded"),
            ("done", "Backend connected", "FastAPI running on port 8000"),
            ("done", "Data loaded", f"{_stats['total_chunks']} chunks \u2022 {len(_sources)} sources"),
            ("active", "Verifying models", "Checking Llama 3.2 + embeddings..."),
        ]), unsafe_allow_html=True)
        time.sleep(0.5)

        # Stage 5: All done
        _loader.markdown(timeline_html([
            ("done", "Interface ready", "All components loaded"),
            ("done", "Backend connected", "FastAPI running on port 8000"),
            ("done", "Data loaded", f"{_stats['total_chunks']} chunks \u2022 {len(_sources)} sources"),
            ("done", "Models verified", "Llama 3.2 + MiniLM embeddings"),
        ], footer="\u2713 All systems go!"), unsafe_allow_html=True)
        time.sleep(0.7)
    else:
        # Backend offline
        _loader.markdown(timeline_html([
            ("done", "Interface ready", "All components loaded"),
            ("active", "Backend offline", "Run: uvicorn api:app --reload --port 8000"),
            ("pending", "Load indexed data", ""),
            ("pending", "Verify models", ""),
        ]), unsafe_allow_html=True)
        time.sleep(1.5)

    _loader.empty()
    st.session_state.app_ready = True
    st.rerun()

# ── Prefetch data (cached from loader — instant) ────────────────────────────
api_ok = check_health()
sources_list = get_sources() if api_ok else []
stats = get_stats() if api_ok else {"total_chunks": 0}

# ── Transitions ─────────────────────────────────────────────────────────────
if st.session_state.transition == "new_chat":
    new_conversation()
    st.session_state.transition = None
    st.rerun()

if st.session_state.transition == "switch_chat":
    target = getattr(st.session_state, "_switch_target", None)
    if target and target in st.session_state.conversations:
        st.session_state.current_conv = target
        st.session_state.editing_idx = None
        st.session_state._switch_target = None
    st.session_state.transition = None
    st.rerun()

# ── Sidebar (uses pre-fetched data, no API calls) ───────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding: 0.3rem 0 0.8rem 0;">
        <div style="font-size:1.8rem; font-weight:700;">{APP_EMOJI} {APP_NAME}</div>
        <div style="font-size:0.7rem; color:#666;">Private \u2022 Local \u2022 Fast</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
    if st.button("\u2795  New Chat", use_container_width=True, key="new_chat"):
        st.session_state.transition = "new_chat"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    search = st.text_input(
        "Search",
        placeholder="\U0001f50d Search conversations...",
        label_visibility="collapsed",
        key="chat_search",
    )

    st.markdown("---")

    conv_order = st.session_state.conv_order
    conversations = st.session_state.conversations

    if conv_order:
        filtered = conv_order
        if search:
            filtered = [
                cid for cid in conv_order
                if cid in conversations
                and search.lower() in conversations[cid].get("title", "").lower()
            ]

        for cid in filtered:
            if cid not in conversations:
                continue
            conv = conversations[cid]
            title = conv.get("title", "New Chat")
            is_active = cid == st.session_state.current_conv

            col1, col2 = st.columns([6, 1])
            with col1:
                label = f"\u25b8 {title}" if is_active else f"  {title}"
                if st.button(label, key=f"conv_{cid}", use_container_width=True):
                    if cid != st.session_state.current_conv:
                        st.session_state.transition = "switch_chat"
                        st.session_state._switch_target = cid
                    st.rerun()
            with col2:
                st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                if st.button("\U0001f5d1", key=f"del_{cid}"):
                    delete_conversation(cid)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        if not filtered and search:
            st.caption("No matching conversations.")
    else:
        st.caption("No chats yet. Start one!")

    # Source filter (uses pre-fetched sources_list)
    st.markdown("---")
    if sources_list:
        source_options = ["All Sources"] + sources_list
        selected_source = st.selectbox(
            "\U0001f50d Filter by source",
            source_options,
            key="src_filter",
            label_visibility="collapsed",
        )
    else:
        selected_source = "All Sources"


# ── Main Content ─────────────────────────────────────────────────────────────

if not api_ok:
    st.error("\u26a0\ufe0f **API is offline.** Start the backend first:")
    st.code("uvicorn api:app --reload --port 8000", language="bash")
    st.stop()

# ── Welcome Screen ───────────────────────────────────────────────────────────

if not st.session_state.current_conv:
    st.markdown(f"""
    <div class="welcome">
        <h2>{APP_EMOJI} {APP_NAME}</h2>
        <p class="tagline">Ask anything about your documents. Everything stays on your machine.</p>
        <div class="welcome-features">
            <div class="feature-chip">\U0001f4c4 PDF & DOCX</div>
            <div class="feature-chip">\U0001f310 Web Pages</div>
            <div class="feature-chip">\U0001f3ac YouTube</div>
            <div class="feature-chip">\U0001f4ca CSV & JSON</div>
            <div class="feature-chip">\U0001f512 100% Private</div>
            <div class="feature-chip">\U0001f999 Llama 3.2</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("\u2795 Start a new chat", use_container_width=True, type="primary"):
            new_conversation()
            st.rerun()
    st.stop()


# ── Render Messages ──────────────────────────────────────────────────────────

messages = get_current_messages()

for idx, msg in enumerate(messages):
    role = msg["role"]
    avatar = "\U0001f9d1\u200d\U0001f4bb" if role == "user" else APP_EMOJI

    with st.chat_message(role, avatar=avatar):
        if role == "user" and st.session_state.editing_idx == idx:
            edited = st.text_area("Edit", value=msg["content"], key=f"edit_{idx}", label_visibility="collapsed", height=100)
            c1, c2, c3 = st.columns([1, 1, 3])
            with c1:
                if st.button("\u2713 Send", key=f"save_{idx}", use_container_width=True, type="primary"):
                    cid = st.session_state.current_conv
                    st.session_state.conversations[cid]["messages"] = messages[:idx]
                    st.session_state.editing_idx = None
                    add_message("user", edited)
                    save_history()
                    st.rerun()
            with c2:
                if st.button("\u2717 Cancel", key=f"cancel_{idx}", use_container_width=True):
                    st.session_state.editing_idx = None
                    st.rerun()
            continue

        st.markdown(msg["content"])

        if role == "assistant" and msg.get("sources"):
            with st.expander(f"\U0001f4da {len(msg['sources'])} sources"):
                for i, src in enumerate(msg["sources"], 1):
                    src_type = src.get("source_type", "?")
                    src_name = src.get("file_name") or src.get("url", "")
                    st.caption(f"**[{i}]** `{src_type}` \u2014 {src_name}")

        if role == "user":
            if st.button("\u270f\ufe0f Edit", key=f"edit_btn_{idx}"):
                st.session_state.editing_idx = idx
                st.rerun()
        elif role == "assistant":
            if st.button("\U0001f4cb Copy", key=f"copy_btn_{idx}"):
                st.code(msg["content"], language=None)
                st.toast("Select the text above and copy it.", icon="\U0001f4cb")


# ── Generate Response ────────────────────────────────────────────────────────

messages = get_current_messages()

if (
    messages
    and messages[-1]["role"] == "user"
    and (len(messages) < 2 or messages[-2]["role"] != "assistant")
    and st.session_state.editing_idx is None
):
    question = messages[-1]["content"]

    with st.chat_message("assistant", avatar=APP_EMOJI):
        if stats["total_chunks"] == 0:
            st.info("\U0001f4ed No documents indexed yet. Go to **Knowledge Base** to add some sources first.")
            add_message("assistant", "No documents indexed yet. Please add sources in the Knowledge Base page first.")
        else:
            chat_history = []
            for m in messages[:-1]:
                if m["role"] in ("user", "assistant"):
                    chat_history.append({"role": m["role"], "content": m["content"]})

            with st.status(f"{APP_EMOJI} Loca is thinking...", expanded=True) as status:
                try:
                    st.write("\U0001f50d Searching your documents...")
                    st.write("\U0001f3af Re-ranking for best matches...")
                    st.write("\U0001f9e0 Generating answer with Llama 3.2...")
                    result = query_api(
                        question,
                        chat_history=chat_history if chat_history else None,
                        source_filter=selected_source,
                    )
                    status.update(label="\u2728 Answer ready!", state="complete", expanded=False)
                except requests.exceptions.Timeout:
                    status.update(label="\u23f0 Timed out", state="error")
                    st.error("Request timed out. Try again.")
                    st.stop()
                except Exception as e:
                    status.update(label="\u274c Error", state="error")
                    st.error(f"Error: {e}")
                    st.stop()

            answer = result["answer"]
            st.write_stream(stream_response(answer))

            if result.get("sources"):
                with st.expander(f"\U0001f4da {result['num_sources']} sources"):
                    for i, src in enumerate(result["sources"], 1):
                        src_type = src.get("source_type", "?")
                        src_name = src.get("file_name") or src.get("url", "")
                        st.caption(f"**[{i}]** `{src_type}` \u2014 {src_name}")

            add_message("assistant", answer, sources=result.get("sources", []))
    save_history()


# ── Chat Input ───────────────────────────────────────────────────────────────

question = st.chat_input(f"Ask {APP_NAME} anything about your documents...")

if question:
    if not st.session_state.current_conv:
        new_conversation()
    add_message("user", question)
    st.rerun()

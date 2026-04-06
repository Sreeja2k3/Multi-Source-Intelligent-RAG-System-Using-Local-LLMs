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
    show_loader, stream_response, page_loader, quick_loader, brand_bar,
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

# ── Prefetch data ────────────────────────────────────────────────────────────
if "chat_loaded" not in st.session_state:
    _pl = page_loader("\U0001f4ac", "Chat", ["Connecting to backend...", "Loading conversations...", "Fetching sources..."])
    api_ok = check_health()
    sources_list = get_sources() if api_ok else []
    stats = get_stats() if api_ok else {"total_chunks": 0}
    _pl.empty()
    st.session_state.chat_loaded = True
else:
    # Show quick loader only when navigating to chat (not on every message send)
    _show_ql = st.session_state.get("_last_page") != "chat"
    if _show_ql:
        _ql = quick_loader("Loading chat...")
    api_ok = check_health()
    sources_list = get_sources() if api_ok else []
    stats = get_stats() if api_ok else {"total_chunks": 0}
    if _show_ql:
        _ql.empty()
    st.session_state._last_page = "chat"

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

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # Sidebar-specific CSS for chat list alignment
    st.markdown("""
    <style>
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        align-items: center !important;
        gap: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
        height: 34px !important;
        min-height: 34px !important;
        max-height: 34px !important;
        padding: 0 0.5rem !important;
        font-size: 0.8rem !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Compact brand + new chat on same visual block
    if st.button(f"\u2795  New Chat", use_container_width=True, key="new_chat", type="primary"):
        st.session_state.transition = "new_chat"
        st.rerun()

    search = st.text_input("Search", placeholder="\U0001f50d Search...", label_visibility="collapsed", key="chat_search")

    # Chat list
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

            display = title if len(title) <= 22 else title[:19] + "..."

            c1, c2 = st.columns([7, 1])
            with c1:
                if is_active:
                    st.markdown(f"<div style='padding:0.4rem 0.6rem;background:#1a365d;border-radius:8px;font-size:0.82rem;font-weight:500;color:#93c5fd;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>\U0001f7e2 {display}</div>", unsafe_allow_html=True)
                else:
                    if st.button(f"\u25CF {display}", key=f"conv_{cid}", use_container_width=True):
                        st.session_state.current_conv = cid
                        st.session_state.editing_idx = None
                        st.rerun()
            with c2:
                if st.button("\U0001f5d1", key=f"del_{cid}", help="Delete"):
                    delete_conversation(cid)
                    st.rerun()

        if not filtered and search:
            st.caption("No matches found.")
    else:
        st.caption("No conversations yet.")

    # Source filter
    if sources_list:
        st.markdown("---")
        st.caption("\U0001f50d Answer from specific source:")
        source_options = ["All Sources"] + sources_list
        selected_source = st.selectbox("Source filter", source_options, key="src_filter", label_visibility="collapsed", help="Filter responses to only use chunks from this source")
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
    # No st.stop() — chat input below stays visible, typing auto-creates a conversation


# ── Chat message CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
.msg-user {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 0.8rem;
}
.msg-user .bubble {
    background: #2a2a3e;
    padding: 0.8rem 1.1rem;
    border-radius: 18px 18px 4px 18px;
    max-width: 70%;
    font-size: 0.92rem;
    line-height: 1.6;
    color: #e0e0e0;
}
.msg-bot {
    margin-bottom: 0.8rem;
    padding: 0.4rem 0;
}
.msg-bot .text {
    font-size: 0.92rem;
    line-height: 1.7;
    color: #d0d0d0;
}
.msg-bot .sources {
    font-size: 0.7rem;
    color: #555;
    margin-top: 0.4rem;
}
.msg-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.6rem;
    margin-top: 0.2rem;
    opacity: 0.3;
    font-size: 0.75rem;
}
.msg-actions:hover { opacity: 0.7; }
</style>
""", unsafe_allow_html=True)

# ── Render Messages ──────────────────────────────────────────────────────────

messages = get_current_messages()

# Check if we're in edit mode
if st.session_state.editing_idx is not None and messages:
    edit_idx = st.session_state.editing_idx
    if edit_idx < len(messages) and messages[edit_idx]["role"] == "user":
        # Render messages before edit point as HTML
        for i in range(edit_idx):
            msg = messages[i]
            if msg["role"] == "user":
                st.markdown(f'<div class="msg-user"><div class="bubble">{msg["content"]}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="msg-bot"><div class="text">{msg["content"]}</div></div>', unsafe_allow_html=True)

        # Edit input using Streamlit widget
        st.markdown('<div style="display:flex;justify-content:flex-end;"><div style="width:70%;">', unsafe_allow_html=True)
        edited = st.text_area("Edit your message", value=messages[edit_idx]["content"], key="edit_area", label_visibility="collapsed", height=80)
        c1, c2, c3 = st.columns([1, 1, 4])
        with c1:
            if st.button("\u2713 Send", key="save_edit", use_container_width=True, type="primary"):
                cid = st.session_state.current_conv
                st.session_state.conversations[cid]["messages"] = messages[:edit_idx]
                st.session_state.editing_idx = None
                add_message("user", edited)
                save_history()
                st.rerun()
        with c2:
            if st.button("\u2717 Cancel", key="cancel_edit", use_container_width=True):
                st.session_state.editing_idx = None
                st.rerun()
        st.markdown('</div></div>', unsafe_allow_html=True)

elif messages:
    # Render all messages as custom HTML
    for idx, msg in enumerate(messages):
        if msg["role"] == "user":
            st.markdown(f'<div class="msg-user"><div class="bubble">{msg["content"]}</div></div>', unsafe_allow_html=True)
            # Edit button (Streamlit widget, right-aligned)
            cols = st.columns([8, 1])
            with cols[1]:
                if st.button("\u270f\ufe0f", key=f"e_{idx}", help="Edit"):
                    st.session_state.editing_idx = idx
                    st.rerun()

        elif msg["role"] == "assistant":
            # Sources
            src_line = ""
            if msg.get("sources"):
                src_names = []
                for src in msg["sources"]:
                    name = src.get("file_name") or src.get("url", "")
                    if name and name not in src_names:
                        src_names.append(name)
                if src_names:
                    src_line = f'<div class="sources">\u2022 {" \u2022 ".join(src_names)}</div>'

            st.markdown(f'<div class="msg-bot"><div class="text">{msg["content"]}</div>{src_line}</div>', unsafe_allow_html=True)
            # Copy to clipboard using JS
            import html as html_lib
            escaped = html_lib.escape(msg["content"]).replace("\n", "\\n").replace("'", "\\'")
            copy_id = f"copy_{idx}"
            st.markdown(f"""
<button onclick="navigator.clipboard.writeText('{escaped}').then(()=>{{this.innerText='\u2713 Copied!';setTimeout(()=>this.innerText='\U0001f4cb',1500)}})" style="background:transparent;border:1px solid transparent;color:#666;font-size:0.78rem;padding:0.15rem 0.4rem;cursor:pointer;border-radius:6px;transition:all 0.15s;" onmouseover="this.style.borderColor='#444';this.style.color='#aaa'" onmouseout="this.style.borderColor='transparent';this.style.color='#666'">\U0001f4cb</button>
            """, unsafe_allow_html=True)


# ── Chat Input + Response Generation ─────────────────────────────────────────

def generate_response(question_text, history_msgs):
    """Show thinking spinner, call API, stream answer."""
    if stats["total_chunks"] == 0:
        with st.chat_message("assistant", avatar=APP_EMOJI):
            st.info("\U0001f4ed No documents indexed yet. Go to **Knowledge Base** to add some sources first.")
            add_message("assistant", "No documents indexed yet. Please add sources in the Knowledge Base page first.")
        return

    chat_history = []
    for m in history_msgs:
        if m["role"] in ("user", "assistant"):
            chat_history.append({"role": m["role"], "content": m["content"]})

    _thinking = st.empty()
    _thinking.markdown('<div style="display:flex;align-items:center;gap:0.6rem;padding:0.8rem 1rem;color:#93c5fd;font-size:0.85rem;"><div style="width:18px;height:18px;border:2px solid #2a2a4a;border-top:2px solid #60a5fa;border-radius:50%;animation:pg-spin 0.6s linear infinite;"></div>Loca is thinking...</div><style>@keyframes pg-spin{to{transform:rotate(360deg);}}</style>', unsafe_allow_html=True)

    try:
        result = query_api(
            question_text,
            chat_history=chat_history if chat_history else None,
            source_filter=selected_source,
        )
    except requests.exceptions.Timeout:
        _thinking.empty()
        st.error("Request timed out. Try again.")
        return
    except Exception as e:
        _thinking.empty()
        st.error(f"Error: {e}")
        return

    _thinking.empty()

    with st.chat_message("assistant", avatar=APP_EMOJI):
        answer = result["answer"]
        st.write_stream(stream_response(answer))

    add_message("assistant", answer, sources=result.get("sources", []))


# Handle pending response from previous rerun (last msg is user with no reply)
messages = get_current_messages()
if (
    messages
    and messages[-1]["role"] == "user"
    and st.session_state.editing_idx is None
):
    generate_response(messages[-1]["content"], messages[:-1])

# Chat input
new_question = st.chat_input(f"Ask {APP_NAME} anything about your documents...")

if new_question:
    if not st.session_state.current_conv:
        new_conversation()

    # Show the user message immediately
    st.markdown(f'<div class="msg-user"><div class="bubble">{new_question}</div></div>', unsafe_allow_html=True)
    add_message("user", new_question)

    # Generate response right here — no rerun
    generate_response(new_question, get_current_messages()[:-1])

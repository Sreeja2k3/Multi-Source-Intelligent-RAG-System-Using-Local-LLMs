# ui/shared.py — Shared utilities for Loca multi-page app

import json
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

# ── Config ───────────────────────────────────────────────────────────────────
API_URL = "http://localhost:8000"
HISTORY_FILE = Path(__file__).parent / "chat_history.json"
APP_NAME = "Loca"
APP_EMOJI = "\U0001f999"
APP_TAGLINE = "Your private, local AI assistant"


# ── Theme CSS ────────────────────────────────────────────────────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Hide defaults */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* Main container */
.block-container {
    padding-top: 1.2rem !important;
    padding-bottom: 0rem !important;
    max-width: 900px !important;
}

/* ── Sidebar ───────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background-color: #0f1117;
    border-right: 1px solid #1e1e2e;
}

section[data-testid="stSidebar"] .block-container {
    padding-top: 0.8rem;
}

section[data-testid="stSidebar"] .stTextInput input {
    background-color: #1a1a2e !important;
    border: 1px solid #2a2a4a !important;
    border-radius: 8px;
    font-size: 0.85rem;
}

section[data-testid="stSidebar"] .stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s ease;
    font-size: 0.85rem;
}

/* ── Page header ───────────────────────────────────────── */
.page-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid #1e1e2e;
    margin-bottom: 1.2rem;
}

.page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.3px;
}

.page-header .subtitle {
    font-size: 0.8rem;
    color: #666;
    margin-left: auto;
}

/* ── Cards ─────────────────────────────────────────────── */
.metric-card {
    background: linear-gradient(135deg, #0f1117, #1a1a2e);
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
}

.metric-card .value {
    font-size: 2rem;
    font-weight: 700;
    color: #60a5fa;
}

.metric-card .label {
    font-size: 0.75rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 0.3rem;
}

.info-card {
    background-color: #0f1117;
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}

.info-card h3 {
    font-size: 1rem;
    font-weight: 600;
    margin: 0 0 0.8rem 0;
}

/* ── Chat messages ─────────────────────────────────────── */
div[data-testid="stChatMessage"] {
    padding: 0.8rem 1rem;
    border-radius: 12px;
    margin-bottom: 0.3rem;
}

/* ── Animated loader ───────────────────────────────────── */
@keyframes pulse-dots {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1.2); }
}

@keyframes fade-in {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

.loca-loader {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2.5rem 0;
    gap: 0.8rem;
    animation: fade-in 0.3s ease;
}

.loca-loader .dots {
    display: flex;
    gap: 6px;
}

.loca-loader .dots span {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #60a5fa;
    animation: pulse-dots 1.4s infinite ease-in-out;
}

.loca-loader .dots span:nth-child(1) { animation-delay: 0s; }
.loca-loader .dots span:nth-child(2) { animation-delay: 0.2s; }
.loca-loader .dots span:nth-child(3) { animation-delay: 0.4s; }

.loca-loader .loader-text {
    font-size: 0.9rem;
    color: #93c5fd;
    font-weight: 500;
}

.loca-loader .loader-emoji {
    font-size: 1.5rem;
}

/* ── Status widget ─────────────────────────────────────── */
div[data-testid="stStatusWidget"] {
    border-radius: 10px !important;
    border: 1px solid #2a2a4a !important;
    background-color: #0e1525 !important;
}

div[data-testid="stStatusWidget"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.85rem;
    color: #93c5fd;
    padding: 0.15rem 0;
}

/* ── New Chat button ───────────────────────────────────── */
.new-chat-btn > button {
    background-color: #2563eb !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

.new-chat-btn > button:hover {
    background-color: #1d4ed8 !important;
}

/* ── Delete button ─────────────────────────────────────── */
.delete-btn > button {
    background-color: transparent !important;
    color: #ef4444 !important;
    border: 1px solid #ef4444 !important;
    font-size: 0.75rem !important;
    padding: 0.2rem 0.4rem !important;
}

.delete-btn > button:hover {
    background-color: #ef4444 !important;
    color: white !important;
}

/* ── Source card ────────────────────────────────────────── */
.source-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.7rem 1rem;
    background-color: #0f1117;
    border: 1px solid #2a2a4a;
    border-radius: 10px;
    margin-bottom: 0.4rem;
}

.source-item .name {
    font-size: 0.85rem;
    font-weight: 500;
    color: #e0e0e0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 70%;
}

.source-item .badge {
    font-size: 0.7rem;
    padding: 0.15rem 0.5rem;
    border-radius: 12px;
    background-color: #1a365d;
    color: #93c5fd;
}

/* ── Welcome screen ────────────────────────────────────── */
.welcome {
    text-align: center;
    padding: 3rem 2rem;
    animation: fade-in 0.5s ease;
}

.welcome h2 {
    font-size: 2.5rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}

.welcome .tagline {
    color: #666;
    font-size: 1rem;
    margin-bottom: 2rem;
}

.welcome-features {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.6rem;
    margin-top: 1.5rem;
}

.feature-chip {
    background-color: #1a1a2e;
    color: #93c5fd;
    padding: 0.5rem 1.2rem;
    border-radius: 20px;
    font-size: 0.82rem;
    border: 1px solid #2a2a4a;
    transition: all 0.2s ease;
}

.feature-chip:hover {
    border-color: #60a5fa;
    background-color: #1a365d;
}

/* ── Ingest card ───────────────────────────────────────── */
.ingest-card {
    background-color: #0f1117;
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    transition: border-color 0.2s ease;
    height: 100%;
}

.ingest-card:hover {
    border-color: #60a5fa;
}

.ingest-card .icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
}

.ingest-card h4 {
    font-size: 0.95rem;
    font-weight: 600;
    margin: 0 0 0.3rem 0;
}

.ingest-card p {
    font-size: 0.75rem;
    color: #888;
    margin: 0;
}

/* ── Skeleton loading ──────────────────────────────────── */
@keyframes skeleton-shimmer {
    0% { background-position: -400px 0; }
    100% { background-position: 400px 0; }
}

.skeleton {
    background: linear-gradient(90deg, #1a1a2e 25%, #252540 37%, #1a1a2e 63%);
    background-size: 800px 100%;
    animation: skeleton-shimmer 1.5s ease-in-out infinite;
    border-radius: 8px;
}

.skel-card {
    height: 90px;
    border-radius: 12px;
    margin-bottom: 0.8rem;
}

.skel-line {
    height: 14px;
    margin-bottom: 0.6rem;
    border-radius: 6px;
}

.skel-line.w80 { width: 80%; }
.skel-line.w60 { width: 60%; }
.skel-line.w40 { width: 40%; }
.skel-line.w100 { width: 100%; }

.skel-circle {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: inline-block;
}

.skel-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
}

.skel-row > div {
    flex: 1;
}

.skel-msg {
    display: flex;
    gap: 0.8rem;
    align-items: flex-start;
    margin-bottom: 1.2rem;
    padding: 0.8rem;
}

.skel-msg-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.skel-header {
    height: 28px;
    width: 200px;
    border-radius: 8px;
    margin-bottom: 1.2rem;
}

.skel-input {
    height: 45px;
    border-radius: 12px;
    margin-top: 2rem;
}

.skel-chip-row {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    flex-wrap: wrap;
    margin-top: 1rem;
}

.skel-chip {
    width: 90px;
    height: 32px;
    border-radius: 20px;
}

.skel-container {
    animation: fade-in 0.2s ease;
    padding: 1rem 0;
}

/* ── Chat input ────────────────────────────────────────── */
div[data-testid="stChatInput"] textarea {
    border-radius: 12px !important;
    font-size: 0.95rem;
}

/* ── Scrollbar ─────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #444; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #666; }

/* ── Danger zone ───────────────────────────────────────── */
.danger-zone {
    border: 1px solid #7f1d1d;
    border-radius: 12px;
    padding: 1.2rem;
    background-color: #1a0505;
    margin-top: 1rem;
}

.danger-zone h4 {
    color: #ef4444;
    font-size: 0.9rem;
    margin: 0 0 0.5rem 0;
}

/* ── Tech badge ────────────────────────────────────────── */
.tech-badge {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 500;
    background-color: #1a1a2e;
    border: 1px solid #2a2a4a;
    color: #c0c0d0;
    margin: 0.2rem;
}
</style>
"""


# ── API Helpers (cached 30s to keep page loads fast) ─────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def check_health():
    try:
        return requests.get(f"{API_URL}/health", timeout=2).status_code == 200
    except Exception:
        return False

@st.cache_data(ttl=30, show_spinner=False)
def get_health_info():
    try:
        return requests.get(f"{API_URL}/health", timeout=2).json()
    except Exception:
        return {"status": "offline", "model": "unknown"}

@st.cache_data(ttl=30, show_spinner=False)
def get_stats():
    try:
        return requests.get(f"{API_URL}/stats", timeout=2).json()
    except Exception:
        return {"total_chunks": 0, "collection": "unknown"}

@st.cache_data(ttl=30, show_spinner=False)
def get_sources():
    try:
        return requests.get(f"{API_URL}/sources", timeout=2).json().get("sources", [])
    except Exception:
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

def ingest_file_api(file_bytes, filename):
    r = requests.post(f"{API_URL}/ingest/file", files={"file": (filename, file_bytes)}, timeout=60)
    r.raise_for_status()
    return r.json()

def ingest_url_api(url):
    r = requests.post(f"{API_URL}/ingest/url", json={"url": url}, timeout=30)
    r.raise_for_status()
    return r.json()

def ingest_youtube_api(url):
    r = requests.post(f"{API_URL}/ingest/youtube", json={"url": url}, timeout=30)
    r.raise_for_status()
    return r.json()

def delete_source_api(source_name):
    r = requests.delete(f"{API_URL}/source", json={"source_name": source_name}, timeout=10)
    r.raise_for_status()
    return r.json()

def clear_index_api():
    r = requests.delete(f"{API_URL}/clear", timeout=10)
    r.raise_for_status()
    return r.json()


# ── Chat History Persistence ─────────────────────────────────────────────────

def load_history():
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data.get("conversations", {}), data.get("order", [])
        except Exception:
            pass
    return {}, []

def save_history():
    data = {
        "conversations": st.session_state.conversations,
        "order": st.session_state.conv_order,
    }
    HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Session State Init ───────────────────────────────────────────────────────

def init_state():
    if "conversations" not in st.session_state:
        convs, order = load_history()
        st.session_state.conversations = convs
        st.session_state.conv_order = order
    if "current_conv" not in st.session_state:
        st.session_state.current_conv = None
    if "editing_idx" not in st.session_state:
        st.session_state.editing_idx = None
    if "transition" not in st.session_state:
        st.session_state.transition = None
    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False
    if "confirm_delete_src" not in st.session_state:
        st.session_state.confirm_delete_src = None


# ── Conversation Helpers ─────────────────────────────────────────────────────

def new_conversation():
    conv_id = str(uuid.uuid4())[:8]
    st.session_state.conversations[conv_id] = {
        "title": "New Chat",
        "messages": [],
        "created": datetime.now().isoformat(),
    }
    st.session_state.conv_order.insert(0, conv_id)
    st.session_state.current_conv = conv_id
    st.session_state.editing_idx = None
    save_history()
    return conv_id

def delete_conversation(conv_id):
    if conv_id in st.session_state.conversations:
        del st.session_state.conversations[conv_id]
    if conv_id in st.session_state.conv_order:
        st.session_state.conv_order.remove(conv_id)
    if st.session_state.current_conv == conv_id:
        st.session_state.current_conv = (
            st.session_state.conv_order[0] if st.session_state.conv_order else None
        )
    save_history()

def get_current_messages():
    cid = st.session_state.current_conv
    if cid and cid in st.session_state.conversations:
        return st.session_state.conversations[cid]["messages"]
    return []

def add_message(role, content, sources=None):
    cid = st.session_state.current_conv
    if not cid:
        return
    msg = {"role": role, "content": content}
    if sources:
        msg["sources"] = sources
    st.session_state.conversations[cid]["messages"].append(msg)
    msgs = st.session_state.conversations[cid]["messages"]
    user_msgs = [m for m in msgs if m["role"] == "user"]
    if len(user_msgs) == 1:
        title = user_msgs[0]["content"].strip()
        st.session_state.conversations[cid]["title"] = (
            title[:40] + "..." if len(title) > 40 else title
        )
    save_history()


# ── UI Components ────────────────────────────────────────────────────────────

def show_loader(emoji, message):
    st.markdown(f"""
    <div class="loca-loader">
        <div class="loader-emoji">{emoji}</div>
        <div class="dots"><span></span><span></span><span></span></div>
        <div class="loader-text">{message}</div>
    </div>
    """, unsafe_allow_html=True)

def stream_response(text):
    words = text.split(" ")
    for i, word in enumerate(words):
        yield word + (" " if i < len(words) - 1 else "")
        time.sleep(0.02)

def page_header(icon, title, subtitle=""):
    sub_html = f'<span class="subtitle">{subtitle}</span>' if subtitle else ""
    st.markdown(f"""
    <div class="page-header">
        <h1>{icon} {title}</h1>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)

def metric_card(value, label):
    return f"""
    <div class="metric-card">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """

def apply_theme():
    if "theme_applied" not in st.session_state:
        st.session_state.theme_applied = True
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

def require_api():
    """Check API health and show error if offline. Returns True if API is OK."""
    if not check_health():
        st.error("\u26a0\ufe0f **API is offline.** Start the backend first:")
        st.code("uvicorn api:app --reload --port 8000", language="bash")
        return False
    return True


# ── Skeleton Screens ─────────────────────────────────────────────────────────

def skeleton_chat():
    """Branded skeleton for chat welcome — shows Loca identity while loading."""
    return """
    <div class="skel-container">
        <div style="display:flex;flex-direction:column;align-items:center;padding:3rem 0 2rem 0;">
            <div style="font-size:3.5rem;animation:breathe 2s ease-in-out infinite;">\U0001f999</div>
            <div style="font-size:2rem;font-weight:700;margin:0.5rem 0;
                background:linear-gradient(90deg,#60a5fa,#a78bfa,#60a5fa);
                background-size:200% auto;-webkit-background-clip:text;
                -webkit-text-fill-color:transparent;animation:shimmer 3s linear infinite;">
                Loca
            </div>
            <div style="color:#555;font-size:0.85rem;margin-bottom:2rem;">
                Setting up your workspace...
            </div>
            <div class="skel-chip-row">
                <div class="skeleton skel-chip"></div>
                <div class="skeleton skel-chip" style="width:100px;"></div>
                <div class="skeleton skel-chip" style="width:80px;"></div>
                <div class="skeleton skel-chip" style="width:95px;"></div>
                <div class="skeleton skel-chip" style="width:110px;"></div>
                <div class="skeleton skel-chip" style="width:85px;"></div>
            </div>
            <div style="margin-top:2.5rem;display:flex;gap:6px;">
                <span style="width:8px;height:8px;border-radius:50%;background:#60a5fa;animation:pulse-dots 1.4s infinite ease-in-out;animation-delay:0s;"></span>
                <span style="width:8px;height:8px;border-radius:50%;background:#60a5fa;animation:pulse-dots 1.4s infinite ease-in-out;animation-delay:0.2s;"></span>
                <span style="width:8px;height:8px;border-radius:50%;background:#60a5fa;animation:pulse-dots 1.4s infinite ease-in-out;animation-delay:0.4s;"></span>
            </div>
        </div>
        <div style="max-width:500px;margin:1rem auto;">
            <div class="skeleton skel-input"></div>
        </div>
    </div>
    <style>
    @keyframes breathe {
        0%, 100% { transform: scale(1); opacity: 0.7; }
        50% { transform: scale(1.08); opacity: 1; }
    }
    @keyframes shimmer {
        0% { background-position: -200% center; }
        100% { background-position: 200% center; }
    }
    @keyframes pulse-dots {
        0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); }
        40% { opacity: 1; transform: scale(1.3); }
    }
    </style>
    """

def skeleton_chat_messages():
    """Branded skeleton for active chat — shows message shapes + loading indicator."""
    return """
    <div class="skel-container">
        <div style="text-align:center;padding:0.5rem 0 1.5rem 0;">
            <span style="font-size:0.8rem;color:#555;">\U0001f999 Loading conversation...</span>
        </div>
        <div class="skel-msg">
            <div class="skeleton skel-circle"></div>
            <div class="skel-msg-body" style="max-width:55%;">
                <div class="skeleton skel-line" style="width:220px;"></div>
                <div class="skeleton skel-line" style="width:160px;"></div>
            </div>
        </div>
        <div class="skel-msg">
            <div class="skeleton skel-circle"></div>
            <div class="skel-msg-body" style="max-width:70%;">
                <div class="skeleton skel-line" style="width:380px;"></div>
                <div class="skeleton skel-line" style="width:320px;"></div>
                <div class="skeleton skel-line" style="width:200px;"></div>
            </div>
        </div>
        <div class="skel-msg">
            <div class="skeleton skel-circle"></div>
            <div class="skel-msg-body" style="max-width:50%;">
                <div class="skeleton skel-line" style="width:180px;"></div>
            </div>
        </div>
        <div class="skel-msg">
            <div class="skeleton skel-circle"></div>
            <div class="skel-msg-body" style="max-width:70%;">
                <div class="skeleton skel-line" style="width:350px;"></div>
                <div class="skeleton skel-line" style="width:280px;"></div>
                <div class="skeleton skel-line" style="width:150px;"></div>
            </div>
        </div>
        <div class="skeleton skel-input" style="margin-top:1.5rem;"></div>
    </div>
    """

def skeleton_knowledge():
    """Branded skeleton for Knowledge Base — shows layout shapes + label."""
    return """
    <div class="skel-container">
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:1.2rem;">
            <span style="font-size:1.3rem;">\U0001f4da</span>
            <span style="font-size:1.2rem;font-weight:600;color:#555;">Loading Knowledge Base...</span>
        </div>
        <div class="skel-row">
            <div><div class="skeleton skel-card"></div></div>
            <div><div class="skeleton skel-card"></div></div>
            <div><div class="skeleton skel-card"></div></div>
        </div>
        <div class="skeleton skel-line w40" style="margin-top:1.5rem;height:20px;"></div>
        <div class="skel-row" style="margin-top:1rem;">
            <div><div class="skeleton skel-card" style="height:160px;"></div></div>
            <div><div class="skeleton skel-card" style="height:160px;"></div></div>
            <div><div class="skeleton skel-card" style="height:160px;"></div></div>
        </div>
        <div class="skeleton skel-line w40" style="margin-top:1.5rem;height:20px;"></div>
        <div style="margin-top:1rem;">
            <div class="skeleton skel-line w100" style="height:45px;margin-bottom:0.5rem;border-radius:10px;"></div>
            <div class="skeleton skel-line w100" style="height:45px;margin-bottom:0.5rem;border-radius:10px;"></div>
            <div class="skeleton skel-line w100" style="height:45px;border-radius:10px;"></div>
        </div>
    </div>
    """

def skeleton_about():
    """Branded skeleton for About page — shows layout shapes + label."""
    return """
    <div class="skel-container">
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:1.2rem;">
            <span style="font-size:1.3rem;">\u2139\ufe0f</span>
            <span style="font-size:1.2rem;font-weight:600;color:#555;">Loading system info...</span>
        </div>
        <div class="skel-row">
            <div><div class="skeleton skel-card"></div></div>
            <div><div class="skeleton skel-card"></div></div>
            <div><div class="skeleton skel-card"></div></div>
            <div><div class="skeleton skel-card"></div></div>
        </div>
        <div class="skeleton skel-line w40" style="height:20px;margin:1.5rem 0 1rem 0;"></div>
        <div class="skeleton skel-line w100" style="height:14px;"></div>
        <div class="skeleton skel-line w80" style="height:14px;"></div>
        <div class="skeleton skel-line w60" style="height:14px;"></div>
        <div class="skeleton skel-line w40" style="height:20px;margin:1.5rem 0 1rem 0;"></div>
        <div class="skeleton skel-line w100" style="height:80px;border-radius:10px;"></div>
        <div class="skeleton skel-line w40" style="height:20px;margin:1.5rem 0 1rem 0;"></div>
        <div class="skel-row">
            <div><div class="skeleton skel-card" style="height:120px;"></div></div>
            <div><div class="skeleton skel-card" style="height:120px;"></div></div>
        </div>
    </div>
    """

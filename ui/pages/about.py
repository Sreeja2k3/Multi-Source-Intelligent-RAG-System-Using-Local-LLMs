# ui/pages/about.py — About & System Status

import streamlit as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import (
    apply_theme, init_state, page_header, metric_card,
    check_health, get_health_info, get_stats, get_sources,
    APP_NAME, APP_EMOJI,
)

apply_theme()
init_state()

# ── Prefetch data ────────────────────────────────────────────────────────────
api_ok = check_health()
health = get_health_info()
stats = get_stats()
sources = get_sources()

page_header("\u2139\ufe0f", "About Loca", "System status & project info")

# ── System Status ────────────────────────────────────────────────────────────

st.markdown("### \U0001f6f0\ufe0f System Status")

c1, c2, c3, c4 = st.columns(4)
with c1:
    status_icon = "\U0001f7e2" if api_ok else "\U0001f534"
    st.markdown(metric_card(status_icon, "API Status"), unsafe_allow_html=True)
with c2:
    st.markdown(metric_card(health.get("model", "?"), "LLM Model"), unsafe_allow_html=True)
with c3:
    st.markdown(metric_card(str(stats["total_chunks"]), "Chunks"), unsafe_allow_html=True)
with c4:
    st.markdown(metric_card(str(len(sources)), "Sources"), unsafe_allow_html=True)

if not api_ok:
    st.markdown("")
    st.warning("API is offline. Start it with:")
    st.code("uvicorn api:app --reload --port 8000", language="bash")


# ── Project Info ───���──────────────────────────────────��──────────────────────

st.markdown("---")
st.markdown("### \U0001f4d6 About This Project")

st.markdown(f"""
**{APP_EMOJI} {APP_NAME}** \u2014 *Multi-Source Intelligent Retrieval-Augmented Generation System Using Local Large Language Models*

A fully local RAG system that ingests documents from multiple source types and answers
questions using a locally hosted LLM. No API keys, no cloud services, complete data privacy.
""")


# ── Architecture ─────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### \U0001f3d7\ufe0f Architecture")

st.markdown("""
```
Documents \u2192 MultiSourceLoader \u2192 DocumentChunker \u2192 VectorStoreManager \u2192 ChromaDB (disk)

Query \u2192 Embedding \u2192 MMR Retrieval (top-5) \u2192 Cross-Encoder Re-ranking
      \u2192 Prompt + Context \u2192 Ollama LLM \u2192 Answer + Sources
```
""")

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="info-card">
        <h3>\U0001f4e5 Ingestion Pipeline</h3>
        <p style="font-size:0.85rem; color:#aaa;">
        \U0001f4c4 PDF \u2022 \U0001f4dd DOCX \u2022 \U0001f4c3 TXT \u2022 \U0001f4ca CSV \u2022 \U0001f4cb JSON<br>
        \U0001f310 Web URLs \u2022 \U0001f3ac YouTube Transcripts<br><br>
        Documents are loaded, cleaned, chunked (512 chars, 50 overlap),
        embedded with sentence-transformers, and stored in ChromaDB with
        SHA-256 deduplication.
        </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="info-card">
        <h3>\U0001f50d Retrieval & Generation</h3>
        <p style="font-size:0.85rem; color:#aaa;">
        MMR search (diversity + relevance)<br>
        Cross-encoder re-ranking for precision<br>
        Conversation memory (6-message window)<br><br>
        Context is formatted and sent to Llama 3.2 via Ollama
        with a system prompt that enforces grounded, source-based answers.
        </p>
    </div>
    """, unsafe_allow_html=True)


# ── Tech Stack ───────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### \U0001f9f0 Tech Stack")

techs = [
    ("Python 3.11", "\U0001f40d"),
    ("LangChain", "\U0001f517"),
    ("Ollama + Llama 3.2", "\U0001f999"),
    ("ChromaDB", "\U0001f4be"),
    ("all-MiniLM-L6-v2", "\U0001f9e0"),
    ("ms-marco Re-ranker", "\U0001f3af"),
    ("FastAPI", "\u26a1"),
    ("Streamlit", "\U0001f3a8"),
    ("Pydantic", "\u2705"),
    ("HuggingFace", "\U0001f917"),
]

badges_html = " ".join(
    f'<span class="tech-badge">{icon} {name}</span>' for name, icon in techs
)
st.markdown(f'<div style="line-height:2.2;">{badges_html}</div>', unsafe_allow_html=True)


# ── How to Run ───────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### \U0001f680 How to Run")

st.code("""# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Ollama and pull model
ollama serve
ollama pull llama3.2

# 3. Start FastAPI backend
uvicorn api:app --reload --port 8000

# 4. Start Streamlit UI
streamlit run ui/app.py""", language="bash")


# ── Footer ─────���─────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(f"""
<div style="text-align:center; padding:1rem 0; color:#555; font-size:0.8rem;">
    {APP_EMOJI} <strong>{APP_NAME}</strong> \u2022 Built with \u2764\ufe0f by Batch 04 \u2022 2025-2026<br>
    Malla Reddy College of Engineering and Technology \u2022 CSE (AI&ML)
</div>
""", unsafe_allow_html=True)

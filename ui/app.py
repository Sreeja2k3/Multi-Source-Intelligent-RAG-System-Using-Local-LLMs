# ui/app.py — Loca: Main Entry Point
# Run with: streamlit run ui/app.py

import sys
import time
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

st.set_page_config(
    page_title="Loca",
    page_icon="\U0001f999",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Navigation (always runs) ────────────────────────────────────────────────
chat_page = st.Page("pages/chat.py", title="Chat", icon="\U0001f4ac", default=True)
knowledge_page = st.Page("pages/knowledge.py", title="Knowledge Base", icon="\U0001f4da")
about_page = st.Page("pages/about.py", title="About", icon="\u2139\ufe0f")

nav = st.navigation([chat_page, knowledge_page, about_page])
nav.run()

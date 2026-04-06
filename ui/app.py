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

# ── Logo above navigation ────────────────────────────────────────────────────
_logo_path = Path(__file__).parent / "assets" / "logo.png"
_icon_path = Path(__file__).parent / "assets" / "logo_icon.png"
st.logo(str(_logo_path), icon_image=str(_icon_path), size="large")

# ── Navigation ───────────────────────────────────────────────────────────────
chat_page = st.Page("pages/chat.py", title="Chat", icon="\U0001f4ac", default=True)
knowledge_page = st.Page("pages/knowledge.py", title="Knowledge Base", icon="\U0001f4da")
about_page = st.Page("pages/about.py", title="About", icon="\u2139\ufe0f")

nav = st.navigation([chat_page, knowledge_page, about_page])
nav.run()

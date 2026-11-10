@echo off
title Starting Multi-Source RAG System...
cd /d "%~dp0"

echo ========================================================
echo Starting FastAPI Backend on http://localhost:8000
echo ========================================================
start "RAG Backend" cmd /k "py -3.11 -m uvicorn api:app --port 8000"

echo Waiting 3 seconds for backend initialization...
timeout /t 3 /nobreak >nul

echo ========================================================
echo Starting Streamlit UI on http://localhost:8501
echo ========================================================
start "RAG Frontend" cmd /k "py -3.11 -m streamlit run ui/app.py"


@echo off
title Stopping Multi-Source RAG System...
echo ========================================================
echo Stopping running RAG servers on ports 8000 and 8501...
echo ========================================================
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501 ^| findstr LISTENING') do taskkill /F /PID %%a 2>nul
echo All RAG servers have been stopped.
timeout /t 2 /nobreak >nul


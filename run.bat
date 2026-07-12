@echo off
REM ── Kronos Stock App launcher ──────────────────────────────────────────
REM Double-click this file to start the app. It opens in your browser.
REM Close this black window to stop the app.
title Kronos Stock App
cd /d "%~dp0"

echo Starting Kronos Stock App...
echo Your browser will open at http://localhost:8501
echo (Keep this window open while using the app. Close it to stop.)
echo.

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m streamlit run app.py --server.port 8501
) else (
    python -m streamlit run app.py --server.port 8501
)

pause

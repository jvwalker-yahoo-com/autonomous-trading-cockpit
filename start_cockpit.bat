@echo off
title Autonomous Stock Trading System Cockpit
echo =====================================================================
echo    AUTONOMOUS STOCK TRADING SYSTEM // PREDICTIVE COCKPIT
echo =====================================================================
cd /d "%~dp0"

echo [1/3] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your system PATH!
    pause
    exit /b 1
)

echo [2/3] Installing / Verifying dependencies...
pip install -r requirements.txt --quiet

echo [3/3] Launching Autonomous Trading Cockpit on http://localhost:8000 ...
timeout /t 2 /nobreak >nul
start "" http://localhost:8000
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000
pause

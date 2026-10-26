@echo off
title Autonomous Trading Cockpit + Cloudflare Tunnel (Live Public Access)
echo =====================================================================
echo    AUTONOMOUS TRADING COCKPIT // 24/7 LIVE HTTPS TUNNEL
echo =====================================================================
cd /d "%~dp0"

echo [1/3] Starting Local Cockpit Server on http://localhost:8000 ...
start "Cockpit Backend Server" python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000

echo [2/3] Waiting for backend initialization...
timeout /t 3 /nobreak >nul

echo [3/3] Launching Cloudflare Tunnel for secure public HTTPS access (No Card Required)...
echo.
echo ---------------------------------------------------------------------
echo Watch below for your live public HTTPS URL (e.g. https://...trycloudflare.com):
echo ---------------------------------------------------------------------
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:8000
pause

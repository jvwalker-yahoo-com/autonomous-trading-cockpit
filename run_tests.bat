@echo off
title Run Autonomous Stock Trading System Test Suite
echo =====================================================================
echo    RUNNING AUTONOMOUS TRADING ENGINE TEST SUITE
echo =====================================================================
cd /d "%~dp0"

python -m pytest tests/test_engine.py -v
echo =====================================================================
pause

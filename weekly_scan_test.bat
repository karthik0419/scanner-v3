@echo off
title SwingU - Weekly Scan (TEST)
REM ============================================================
REM SwingU - Weekly Scan (TEST / personal)
REM Uses SwingU bot (.env) -> sends to private chat
REM Run this manually when you want to test the weekly scan
REM Output shows on screen in real-time (~10-15 min)
REM Start/end timestamps logged to logs\weekly_scan_test.log
REM ============================================================

cd /d F:\projects\claude\scanner-v3

if not exist logs mkdir logs
echo ============================================================
echo  SwingU Weekly Scan (TEST)
echo  Time: %date% %time%
echo  Bot: SwingU (private chat 1121884245)
echo  This takes ~10-15 minutes. Please wait...
echo ============================================================
echo.

echo [%date% %time%] Starting weekly scan (SwingU test) >> logs\weekly_scan_test.log

REM Run scan - output shows on screen in real-time
python scanner.py --max-price 5000 --no-sync

echo.
echo ============================================================
echo  Weekly scan complete (exit code %errorlevel%)
echo  Timestamps logged: logs\weekly_scan_test.log
echo ============================================================
echo [%date% %time%] Weekly scan complete (exit code %errorlevel%) >> logs\weekly_scan_test.log
echo ============================================================ >> logs\weekly_scan_test.log
pause

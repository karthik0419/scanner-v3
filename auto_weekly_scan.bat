@echo off
title SwingIQ - Auto Weekly Scan (PRODUCTION)
REM ============================================================
REM SwingIQ - Auto Weekly Scan (PRODUCTION)
REM Runs automatically via Windows Task Scheduler (Saturdays 09:00)
REM Posts top 30 weekly setups to SwingIQ Telegram channel
REM Uses --env-file flag (no .env swapping needed)
REM Full output logged to logs\auto_weekly.log
REM No pause - this is a cron job (Task Scheduler)
REM ============================================================

cd /d F:\projects\claude\scanner-v3

if not exist logs mkdir logs
echo ============================================================
echo  SwingIQ Auto Weekly Scan (PRODUCTION - cron job)
echo  Time: %date% %time%
echo  Bot: SwingIQ (channel -1004275742331)
echo  Full output: logs\auto_weekly.log
echo  This takes ~10-15 minutes...
echo ============================================================
echo.

echo ============================================================ >> logs\auto_weekly.log
echo [%date% %time%] Starting weekly scan >> logs\auto_weekly.log

REM Run scan with SwingIQ bot via --env-file (full output to log)
python scanner.py --max-price 5000 --no-sync --env-file .env.swingiq >> logs\auto_weekly.log 2>&1

echo  Scan complete (exit code %errorlevel%)
echo  Full log: logs\auto_weekly.log
echo [%date% %time%] Weekly scan complete (exit code %errorlevel%) >> logs\auto_weekly.log
echo ============================================================ >> logs\auto_weekly.log

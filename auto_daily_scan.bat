@echo off
title SwingIQ - Auto Daily Scan (PRODUCTION)
REM ============================================================
REM SwingIQ - Auto Daily Scan (PRODUCTION)
REM Runs automatically via Windows Task Scheduler (08:30 daily)
REM
REM TWO-STEP PROCESS:
REM   1. scanner.py --smart  →  fresh pattern setups CSV (5-8 min)
REM      Scans Backbone50 + Nifty500 + hot sector stocks (~500-800)
REM      Generates results/v3_YYYY-MM-DD.csv with today's picks
REM
REM   2. daily_scan.py        →  volume movers + loads fresh CSV (30 sec)
REM      Posts combined message to SwingIQ Telegram channel:
REM        - PATTERN SETUPS (fresh from step 1, with NEW/Day N labels)
REM        - Volume movers (today's surges)
REM        - Sector heat map
REM
REM Total time: ~6-9 min (well within 8:30-9:15 AM pre-market window)
REM Uses --env-file flag (no .env swapping needed)
REM No pause - this is a cron job (Task Scheduler)
REM ============================================================

cd /d F:\projects\claude\scanner-v3

if not exist logs mkdir logs
echo ============================================================
echo  SwingIQ Auto Daily Scan (PRODUCTION - cron job)
echo  Time: %date% %time%
echo  Bot: SwingIQ (channel -1004275742331)
echo  Step 1: Pattern scan (smart universe, ~5-8 min)
echo  Step 2: Daily volume scan + Telegram (~30 sec)
echo  Full output: logs\auto_daily.log
echo ============================================================
echo.

echo ============================================================ >> logs\auto_daily.log
echo [%date% %time%] Starting daily scan (2-step: pattern + volume) >> logs\auto_daily.log

REM ── Step 1: Fresh pattern scan (smart universe) ──
echo [Step 1/2] Running pattern scan (smart universe)...
echo [%date% %time%] Step 1: scanner.py --smart >> logs\auto_daily.log
python scanner.py --smart --top 30 --min-score 50 --max-price 5000 --no-notify --no-sync --env-file .env.swingiq >> logs\auto_daily.log 2>&1
echo  Pattern scan complete (exit code %errorlevel%)
echo [%date% %time%] Step 1 complete (exit code %errorlevel%) >> logs\auto_daily.log

REM ── Step 2: Daily volume scan + Telegram (loads fresh CSV from step 1) ──
echo [Step 2/2] Running daily volume scan + sending Telegram...
echo [%date% %time%] Step 2: daily_scan.py >> logs\auto_daily.log
python daily_scan.py --top 15 --max-price 5000 --env-file .env.swingiq >> logs\auto_daily.log 2>&1

echo.
echo  Scan complete (exit code %errorlevel%)
echo  Full log: logs\auto_daily.log
echo [%date% %time%] Daily scan complete (exit code %errorlevel%) >> logs\auto_daily.log
echo ============================================================ >> logs\auto_daily.log

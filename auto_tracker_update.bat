@echo off
title SwingIQ - Auto Paper Tracker Update (PRODUCTION)
REM ============================================================
REM SwingIQ - Auto Paper Tracker Update (PRODUCTION)
REM Runs automatically via Windows Task Scheduler (09:15 daily)
REM
REM WHAT IT DOES:
REM   1. python paper_tracker.py update
REM      - Fetches live NSE prices (bhavcopy)
REM      - Checks all WAITING_BREAKOUT picks — enters if price crossed breakout
REM      - Checks all OPEN trades — exits if stop or target hit
REM      - Checks re-entry opportunities for stopped-out trades
REM   2. Sends Telegram alert to SwingIQ channel with:
REM      - New breakouts entered today
REM      - New stop-loss / target hits
REM      - Status of watched picks (AVANTEL, GLENMARK, etc.)
REM
REM Runs at 09:15 IST (after market open, after daily scan at 08:30)
REM Uses --env-file flag for SwingIQ bot (no .env swapping needed)
REM No pause - this is a cron job (Task Scheduler)
REM ============================================================

cd /d F:\projects\claude\scanner-v3

if not exist logs mkdir logs
echo ============================================================
echo  SwingIQ Auto Paper Tracker Update (PRODUCTION - cron job)
echo  Time: %date% %time%
echo  Bot: SwingIQ (channel -1004275742331)
echo  Full output: logs\auto_tracker.log
echo ============================================================
echo.

echo ============================================================ >> logs\auto_tracker.log
echo [%date% %time%] Starting paper tracker update >> logs\auto_tracker.log

REM ── Step 1: Update tracker (fetch prices, check breakouts/stops) ──
echo [Step 1/2] Updating paper tracker...
echo [%date% %time%] Step 1: paper_tracker.py update >> logs\auto_tracker.log
python paper_tracker.py update >> logs\auto_tracker.log 2>&1
echo  Tracker update complete (exit code %errorlevel%)
echo [%date% %time%] Step 1 complete (exit code %errorlevel%) >> logs\auto_tracker.log

REM ── Step 2: Send Telegram alert with breakout/stop notifications ──
echo [Step 2/2] Sending Telegram alert...
echo [%date% %time%] Step 2: tracker_alert.py >> logs\auto_tracker.log
python tracker_alert.py --env-file .env.swingiq >> logs\auto_tracker.log 2>&1
echo  Telegram alert sent (exit code %errorlevel%)
echo [%date% %time%] Step 2 complete (exit code %errorlevel%) >> logs\auto_tracker.log

echo.
echo  Tracker update complete (exit code %errorlevel%)
echo  Full log: logs\auto_tracker.log
echo [%date% %time%] Tracker update complete (exit code %errorlevel%) >> logs\auto_tracker.log
echo ============================================================ >> logs\auto_tracker.log

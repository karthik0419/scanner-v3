@echo off
title SwingU - Daily Scan (TEST, 2-step)
REM ============================================================
REM SwingU - Daily Scan (TEST / personal, 2-step)
REM Uses SwingU bot (.env) -> sends to private chat
REM
REM TWO-STEP PROCESS (same as production cron):
REM   1. scanner.py --smart  ->  fresh pattern setups CSV (5-8 min)
REM   2. daily_scan.py        ->  volume movers + loads fresh CSV (30 sec)
REM
REM Output shows on screen in real-time
REM Start/end timestamps logged to logs\daily_scan_test.log
REM ============================================================

cd /d F:\projects\claude\scanner-v3

if not exist logs mkdir logs
echo ============================================================
echo  SwingU Daily Scan (TEST - 2 step)
echo  Time: %date% %time%
echo  Bot: SwingU (private chat 1121884245)
echo  Step 1: Pattern scan (smart universe, ~5-8 min)
echo  Step 2: Daily volume scan + Telegram (~30 sec)
echo ============================================================
echo.

echo [%date% %time%] Starting daily scan 2-step (SwingU test) >> logs\daily_scan_test.log

REM ── Step 1: Fresh pattern scan (smart universe) ──
echo [Step 1/2] Running pattern scan (smart universe)...
echo [%date% %time%] Step 1: scanner.py --smart >> logs\daily_scan_test.log
python scanner.py --smart --top 30 --min-score 50 --max-price 5000 --no-notify --no-sync
echo  Pattern scan complete (exit code %errorlevel%)
echo [%date% %time%] Step 1 complete (exit code %errorlevel%) >> logs\daily_scan_test.log

echo.

REM ── Step 2: Daily volume scan + Telegram ──
echo [Step 2/2] Running daily volume scan + sending Telegram...
echo [%date% %time%] Step 2: daily_scan.py >> logs\daily_scan_test.log
python daily_scan.py --top 15 --max-price 5000

echo.
echo ============================================================
echo  Daily scan complete (exit code %errorlevel%)
echo  Timestamps logged: logs\daily_scan_test.log
echo ============================================================
echo [%date% %time%] Daily scan complete (exit code %errorlevel%) >> logs\daily_scan_test.log
echo ============================================================ >> logs\daily_scan_test.log
pause

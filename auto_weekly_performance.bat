@echo off
title SwingIQ - Auto Weekly Performance Report (PRODUCTION)
REM ============================================================
REM SwingIQ - Auto Weekly Performance Report (PRODUCTION)
REM Runs automatically via Windows Task Scheduler (Fridays 18:00)
REM
REM WHAT IT DOES:
REM   1. Finds last Friday's SwingIQ scan picks (v3_YYYY-MM-DD.csv)
REM   2. Fetches current prices for all picks
REM   3. Calculates weekly performance (Mon-Fri)
REM   4. Sends Telegram alert to SwingIQ channel with:
REM      - Overall win rate, avg change, best/worst picks
REM      - Top 3 and bottom 3 performers
REM      - All picks detail (if <= 15 picks)
REM
REM Schedule: Every Friday at 18:00 IST (after market close at 15:30)
REM Uses --env-file flag for SwingIQ bot
REM No pause - this is a cron job (Task Scheduler)
REM ============================================================

cd /d F:\projects\claude\scanner-v3

if not exist logs mkdir logs
echo ============================================================
echo  SwingIQ Auto Weekly Performance Report (PRODUCTION - cron job)
echo  Time: %date% %time%
echo  Bot: SwingIQ (channel -1004275742331)
echo  Full output: logs\auto_weekly_perf.log
echo ============================================================
echo.

echo ============================================================ >> logs\auto_weekly_perf.log
echo [%date% %time%] Starting weekly performance report >> logs\auto_weekly_perf.log

REM Run weekly performance tracker with Telegram alert
python weekly_performance.py --send --env-file .env.swingiq >> logs\auto_weekly_perf.log 2>&1

echo  Performance report complete (exit code %errorlevel%)
echo  Full log: logs\auto_weekly_perf.log
echo [%date% %time%] Weekly performance report complete (exit code %errorlevel%) >> logs\auto_weekly_perf.log
echo ============================================================ >> logs\auto_weekly_perf.log

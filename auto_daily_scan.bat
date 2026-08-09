@echo off
REM ============================================================
REM SwingIQ ? Auto Daily Scan
REM Runs automatically via Windows Task Scheduler
REM Posts top 15 morning setups to Telegram channel
REM ============================================================

cd /d F:\projects\claude\scanner-v3

REM Ensure logs directory exists
if not exist logs mkdir logs

REM Add timestamp to log
echo ============================================================ >> logs\auto_daily.log
echo [%date% %time%] Starting daily scan >> logs\auto_daily.log

REM Run the scan (auto-posts to Telegram)
python daily_scan.py --top 15 >> logs\auto_daily.log 2>&1

echo [%date% %time%] Daily scan complete (exit code %errorlevel%) >> logs\auto_daily.log
echo ============================================================ >> logs\auto_daily.log

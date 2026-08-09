@echo off
REM ============================================================
REM SwingIQ ? Auto Weekly Scan
REM Runs automatically via Windows Task Scheduler (Saturdays)
REM Posts top 30 weekly setups to Telegram channel
REM ============================================================

cd /d F:\projects\claude\scanner-v3

REM Ensure logs directory exists
if not exist logs mkdir logs

REM Add timestamp to log
echo ============================================================ >> logs\auto_weekly.log
echo [%date% %time%] Starting weekly scan >> logs\auto_weekly.log

REM Run the scan (auto-posts to Telegram)
python scanner.py >> logs\auto_weekly.log 2>&1

echo [%date% %time%] Weekly scan complete (exit code %errorlevel%) >> logs\auto_weekly.log
echo ============================================================ >> logs\auto_weekly.log

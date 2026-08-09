@echo off
REM ============================================================
REM SwingIQ - Auto Daily Scan
REM Runs automatically via Windows Task Scheduler
REM Posts top 15 morning setups to SwingIQ Telegram channel
REM ============================================================

cd /d F:\projects\claude\scanner-v3

REM Ensure logs directory exists
if not exist logs mkdir logs

REM Add timestamp to log
echo ============================================================ >> logs\auto_daily.log
echo [%date% %time%] Starting daily scan >> logs\auto_daily.log

REM Swap to SwingIQ bot (production) for automated scans
if exist .env.swingiq (
    copy /Y .env .env.swingu_backup >nul 2>&1
    copy /Y .env.swingiq .env >nul 2>&1
    echo [%date% %time%] Switched to SwingIQ bot >> logs\auto_daily.log
)

REM Run the scan (auto-posts to Telegram via SwingIQ bot)
python daily_scan.py --top 15 >> logs\auto_daily.log 2>&1

REM Restore SwingU bot (testing) for manual CLI use
if exist .env.swingu_backup (
    copy /Y .env.swingu_backup .env >nul 2>&1
    del .env.swingu_backup >nul 2>&1
    echo [%date% %time%] Restored SwingU bot >> logs\auto_daily.log
)

echo [%date% %time%] Daily scan complete (exit code %errorlevel%) >> logs\auto_daily.log
echo ============================================================ >> logs\auto_daily.log

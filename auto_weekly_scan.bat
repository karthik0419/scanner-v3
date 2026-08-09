@echo off
REM ============================================================
REM SwingIQ - Auto Weekly Scan
REM Runs automatically via Windows Task Scheduler (Saturdays)
REM Posts top 30 weekly setups to SwingIQ Telegram channel
REM ============================================================

cd /d F:\projects\claude\scanner-v3

REM Ensure logs directory exists
if not exist logs mkdir logs

REM Add timestamp to log
echo ============================================================ >> logs\auto_weekly.log
echo [%date% %time%] Starting weekly scan >> logs\auto_weekly.log

REM Swap to SwingIQ bot (production) for automated scans
if exist .env.swingiq (
    copy /Y .env .env.swingu_backup >nul 2>&1
    copy /Y .env.swingiq .env >nul 2>&1
    echo [%date% %time%] Switched to SwingIQ bot >> logs\auto_weekly.log
)

REM Run the scan (auto-posts to Telegram via SwingIQ bot)
python scanner.py >> logs\auto_weekly.log 2>&1

REM Restore SwingU bot (testing) for manual CLI use
if exist .env.swingu_backup (
    copy /Y .env.swingu_backup .env >nul 2>&1
    del .env.swingu_backup >nul 2>&1
    echo [%date% %time%] Restored SwingU bot >> logs\auto_weekly.log
)

echo [%date% %time%] Weekly scan complete (exit code %errorlevel%) >> logs\auto_weekly.log
echo ============================================================ >> logs\auto_weekly.log

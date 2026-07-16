@echo off
title Scanner v3 - Weekly Scan
cd /d "%~dp0"
echo.
echo  ========================================
echo    SWING SCANNER v3 - WEEKLY SCAN
echo  ========================================
echo.
echo  [1/3] Running scanner...
python scanner.py --top 30
if errorlevel 1 (
    echo  Scanner failed. Check errors above.
    pause
    exit /b 1
)
echo.
echo  [2/3] Generating charts...
python gen_charts.py
if errorlevel 1 (
    echo  Chart generation failed (non-critical).
)
echo.
echo  [3/3] Sending Telegram notification...
python telegram_notify.py
if errorlevel 1 (
    echo  Telegram failed (non-critical).
)
echo.
echo  ========================================
echo    SCAN COMPLETE
echo  ========================================
echo.
pause

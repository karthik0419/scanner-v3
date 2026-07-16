@echo off
title Scanner v3 - Daily Scan
cd /d "%~dp0"
echo.
echo  Running Daily Morning Scan (v3)...
echo.
python daily_scan.py --top 15
echo.
pause

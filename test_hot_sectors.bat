@echo off
cd /d F:\projects\claude\scanner-v3
echo Testing HOT sectors filter...
echo.
python daily_scan.py --top 5 --defensive --no-notify
pause

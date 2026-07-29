@echo off
title Scanner v3.1 - Daily Scan
cd /d "%~dp0"
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:MENU
cls
echo.
echo  ================================================================
echo                   SCANNER v3.1 - DAILY MORNING
echo  ================================================================
echo.
echo   --- Daily Scans (volume + movers + sectors) ---
echo   1.  Daily scan - Smart universe (auto hot sectors, ~600-800 stocks)
echo   2.  Daily scan - Full NSE EQ universe (~2000+ stocks, slower)
echo   3.  Daily scan + price filter (100-400 Rs)
echo   4.  Daily scan + custom price range
echo   5.  Daily scan + custom sector
echo   6.  Daily bearish scan (weak sectors + short candidates)
echo   7.  Sector rotation heatmap only
echo.
echo   --- Pattern Scan (produces CSV + auto-syncs tracker) ---
echo   8.  Smart pattern scan + price filter (adapts to hot sectors)
echo   9.  Nifty 200 pattern scan + price filter (static list, ~5 min)
echo  10.  Full NSE pattern scan + price filter (slower)
echo  11.  Custom stock list pattern scan
echo.
echo  --- Paper Tracker ---
echo  12. Update prices + show status (run EOD daily)
echo  13. Sync tracker with latest scan (merge new picks)
echo  14. Initialize tracker from latest scan (REPLACES existing)
echo  15. Show tracker status only
echo  16. Show tracker summary (one-line)
echo.
echo  --- Analysis Tools ---
echo  17. Rank today's picks by 2-week profit potential
echo  18. Generate charts for latest scan
echo  19. Telegram alert for latest scan picks
echo.
echo  20.  Exit
echo.
set /p choice="  Enter choice [1-20]: "

if "%choice%"=="1" goto DAILY_DEFAULT
if "%choice%"=="2" goto DAILY_FULL
if "%choice%"=="3" goto DAILY_PRICE
if "%choice%"=="4" goto DAILY_CUSTOM_PRICE
if "%choice%"=="5" goto DAILY_SECTOR
if "%choice%"=="6" goto DAILY_BEARISH
if "%choice%"=="7" goto SECTOR_HEAT
if "%choice%"=="8" goto PATTERN_SMART
if "%choice%"=="9" goto PATTERN_NIFTY200
if "%choice%"=="10" goto PATTERN_FULL
if "%choice%"=="11" goto PATTERN_CUSTOM
if "%choice%"=="12" goto PAPER_UPDATE
if "%choice%"=="13" goto PAPER_SYNC
if "%choice%"=="14" goto PAPER_INIT
if "%choice%"=="15" goto PAPER_STATUS
if "%choice%"=="16" goto PAPER_SUMMARY
if "%choice%"=="17" goto RANK_2WEEK
if "%choice%"=="18" goto GEN_CHARTS
if "%choice%"=="19" goto TELEGRAM
if "%choice%"=="20" exit /b 0
echo  Invalid choice.
pause
goto MENU

:DAILY_DEFAULT
cls
echo  === DAILY SCAN - Smart universe (~600-800 stocks, ~3-5 min) ===
echo  Telegram sent automatically on completion.
echo.
python daily_scan.py --top 15
pause
goto MENU

:DAILY_FULL
cls
echo  === DAILY SCAN - Full NSE EQ universe (~2000+ stocks, ~10-15 min) ===
echo.
python daily_scan.py --top 15 --full --workers 10
pause
goto MENU

:DAILY_PRICE
cls
echo  === DAILY SCAN - Price filter 100-400 Rs ===
echo.
python daily_scan.py --top 15 --min-price 100 --max-price 400
pause
goto MENU

:DAILY_CUSTOM_PRICE
cls
echo  === DAILY SCAN - Custom Price Range ===
echo.
set /p minprice="  Min price (Enter for no limit): "
set /p maxprice="  Max price (Enter for no limit): "
set PRICE_ARGS=
if "%minprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --min-price %minprice%
if "%maxprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --max-price %maxprice%
python daily_scan.py --top 15 %PRICE_ARGS%
pause
goto MENU

:DAILY_SECTOR
cls
echo  === DAILY SCAN - Custom Sector ===
echo  Sectors: METAL AUTO BANK IT PHARMA FMCG ENERGY INFRA REALTY
echo           MEDIA PSU CHEMICALS TEXTILES TELECOM CONSUMER
echo.
set /p sector="  Enter sector name: "
set /p topn="  Show top N stocks [default 15]: "
if "%topn%"=="" set topn=15
python daily_scan.py --sector %sector% --top %topn%
pause
goto MENU

:DAILY_BEARISH
cls
echo  === DAILY BEARISH SCAN - Weak sectors + short candidates ===
echo.
python daily_scan.py --bearish --top 15
pause
goto MENU

:SECTOR_HEAT
cls
echo  === SECTOR ROTATION HEATMAP ===
echo.
python -c "from utils.sector_rotation_v3 import print_sector_heatmap, get_weak_sectors; print_sector_heatmap(); print(); print('  Weak sectors (for bearish scans):'); [print(f'    {s:<16} 5d={p5:+.2f}%%  20d={p20:+.2f}%%') for s,p5,p20 in get_weak_sectors()]"
pause
goto MENU

:PATTERN_SMART
cls
echo  === SMART PATTERN SCAN - Adapts to today's hot sectors ===
echo  Universe: Backbone50 + Nifty500 + ALL stocks in today's hot sectors
echo  Changes daily based on which sectors are booming
echo  (Scanner auto-syncs paper tracker + sends Telegram)
echo.
python scanner.py --top 30 --min-score 50 --min-price 100 --max-price 400 --smart
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE - CSV saved, tracker synced, Telegram sent
pause
goto MENU

:PATTERN_NIFTY200
cls
echo  === NIFTY 200 PATTERN SCAN - Price filter 100-400 Rs (~5 min) ===
echo  (Static list of 178 stocks - does not adapt to market heat)
echo  (Scanner auto-syncs paper tracker + sends Telegram)
echo.
python scanner.py --top 30 --min-score 50 --min-price 100 --max-price 400 --stocks nifty200.txt
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:PATTERN_FULL
cls
echo  === FULL NSE PATTERN SCAN - Price filter 100-400 Rs (slower) ===
echo  (Scanner auto-syncs paper tracker + sends Telegram)
echo.
python scanner.py --top 30 --min-score 50 --min-price 100 --max-price 400
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:PATTERN_CUSTOM
cls
echo  === CUSTOM STOCK LIST PATTERN SCAN ===
echo  Available: backbone50.txt, nifty200.txt, nifty500.txt
echo.
set /p stockfile="  Enter stock list file: "
if "%stockfile%"=="" goto MENU
python scanner.py --top 30 --min-score 50 --stocks "%stockfile%"
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:PAPER_UPDATE
cls
echo  === PAPER TRACKER - Update Prices + Status ===
echo  (Fetches prices, checks breakouts, checks re-entries)
echo  Run this daily after market close.
echo.
python paper_tracker.py update
echo.
python paper_tracker.py status
pause
goto MENU

:PAPER_SYNC
cls
echo  === PAPER TRACKER - Sync with Latest Scan ===
echo  (Merges new scan picks into existing tracker)
echo.
python paper_tracker.py sync
pause
goto MENU

:PAPER_INIT
cls
echo  === PAPER TRACKER - Initialize (REPLACES existing) ===
echo  WARNING: This deletes the current tracker and starts fresh.
echo.
set /p ptconfirm="  Initialize? This replaces existing data. [y/n]: "
if /i not "%ptconfirm%"=="y" goto MENU
python paper_tracker.py init
pause
goto MENU

:PAPER_STATUS
cls
echo  === PAPER TRACKER - Status ===
echo.
python paper_tracker.py status
pause
goto MENU

:PAPER_SUMMARY
cls
echo  === PAPER TRACKER - Summary ===
echo.
python paper_tracker.py summary
pause
goto MENU

:RANK_2WEEK
cls
echo  === RANK TODAY'S PICKS BY 2-WEEK POTENTIAL ===
echo  Uses backtest stats to rank latest scan picks by profit probability.
echo.
python rank_2week.py
pause
goto MENU

:GEN_CHARTS
cls
echo  === GENERATE CHARTS FOR LATEST SCAN ===
echo.
python gen_charts.py
echo  Charts saved to results\charts\
start "" "results\charts"
pause
goto MENU

:TELEGRAM
cls
echo  === TELEGRAM ALERT FOR LATEST SCAN ===
echo  Sends top 10 picks from latest scan CSV to Telegram.
echo.
python telegram_notify.py
pause
goto MENU

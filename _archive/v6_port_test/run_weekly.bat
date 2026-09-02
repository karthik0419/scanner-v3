@echo off
title Scanner v3.1 - Weekly Scan
cd /d "%~dp0"
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:MENU
cls
echo.
echo  ================================================================
echo                   SWING SCANNER v3.1 - WEEKLY
echo  ================================================================
echo.
echo   1.  Full scan (all NSE stocks, top 30)
echo   2.  Full scan + price filter (100-400 Rs)
echo   3.  Full scan + custom price range
echo   4.  Nifty 200 scan + price filter (faster, ~5 min)
echo   5.  Smart scan + price filter (adapts to today's hot sectors)
echo   6.  Custom stock list scan
echo   7.  Bearish scan (short setups in weak sectors)
echo   8.  Quick test (50 stocks only)
echo   9.  Scan by timeframe (daily / weekly / monthly only)
echo.
echo   --- Backtest ---
echo  10.  Backtest v3.1 vs v2 (backbone50, in-sample, ~5 min)
echo  11.  Backtest v3.1 vs v2 (nifty200, out-of-sample, ~15 min)
echo  12.  Backtest v3.1 only (backbone50, ~3 min)
echo  13.  ATR multiplier sweep (find optimal stop distance)
echo.
echo  --- Paper Tracker ---
echo  14.  Update prices + show status (run daily after market close)
echo  15.  Sync tracker with latest scan (merge new picks)
echo  16.  Initialize tracker from latest scan (REPLACES existing)
echo  17.  Show tracker status only
echo  18.  Show tracker summary (one-line)
echo.
echo  --- Analysis Tools ---
echo  19.  Whipsaw analysis (find SL exits that would have hit target)
echo  20.  Rank today's picks by 2-week profit potential
echo  21.  Generate charts for latest scan
echo  22.  Enhanced scan (full 15-pattern + pct_done/left + [S][N][D] flags)
echo  23.  Tracker status (send to Telegram)
echo.
echo  24.  Exit
echo.
set /p choice="  Enter choice [1-24]: "

if "%choice%"=="1" goto FULL_SCAN
if "%choice%"=="2" goto PRICE_FILTER
if "%choice%"=="3" goto CUSTOM_PRICE
if "%choice%"=="4" goto NIFTY200
if "%choice%"=="5" goto SMART_SCAN
if "%choice%"=="6" goto CUSTOM_STOCKS
if "%choice%"=="7" goto BEARISH
if "%choice%"=="8" goto TEST_MODE
if "%choice%"=="9" goto TIMEFRAME_SCAN
if "%choice%"=="10" goto BACKTEST_COMPARE
if "%choice%"=="11" goto BACKTEST_NIFTY200
if "%choice%"=="12" goto BACKTEST_V3
if "%choice%"=="13" goto SWEEP_ATR
if "%choice%"=="14" goto PAPER_UPDATE
if "%choice%"=="15" goto PAPER_SYNC
if "%choice%"=="16" goto PAPER_INIT
if "%choice%"=="17" goto PAPER_STATUS
if "%choice%"=="18" goto PAPER_SUMMARY
if "%choice%"=="19" goto WHIPSAW
if "%choice%"=="20" goto RANK_2WEEK
if "%choice%"=="21" goto GEN_CHARTS
if "%choice%"=="22" goto ENHANCED_SCAN
if "%choice%"=="23" goto TRACKER_STATUS
if "%choice%"=="24" exit /b 0
echo  Invalid choice.
pause
goto MENU

:FULL_SCAN
cls
echo  === FULL SCAN - All NSE stocks, top 30 ===
echo  (Scanner auto-syncs paper tracker + sends Telegram)
echo.
python scanner.py --top 30 --min-score 50
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE - Results in results\ folder
pause
goto MENU

:PRICE_FILTER
cls
echo  === FULL SCAN - Price filter 100-400 Rs ===
echo.
python scanner.py --top 30 --min-score 50 --min-price 100 --max-price 400
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:CUSTOM_PRICE
cls
echo  === FULL SCAN - Custom Price Range ===
echo.
set /p minprice="  Min price (Enter for no limit): "
set /p maxprice="  Max price (Enter for no limit): "
set PRICE_ARGS=
if "%minprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --min-price %minprice%
if "%maxprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --max-price %maxprice%
python scanner.py --top 30 --min-score 50 %PRICE_ARGS%
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:NIFTY200
cls
echo  === NIFTY 200 SCAN - Price filter 100-400 Rs (~5 min) ===
echo  (Static list of 178 stocks — does not adapt to market heat)
echo.
python scanner.py --top 30 --min-score 50 --min-price 100 --max-price 400 --stocks nifty200.txt
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:SMART_SCAN
cls
echo  === SMART SCAN - Adapts to today's hot sectors ===
echo  Universe: Backbone50 + Nifty500 + ALL stocks in today's hot sectors
echo  Changes daily based on which sectors are booming
echo.
python scanner.py --top 30 --min-score 50 --min-price 100 --max-price 400 --smart
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:CUSTOM_STOCKS
cls
echo  === CUSTOM STOCK LIST SCAN ===
echo  Available: backbone50.txt, nifty200.txt, nifty500.txt
echo  Or enter your own file path (one symbol per line)
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

:BEARISH
cls
echo  === BEARISH SCAN - Short setups in weak sectors ===
echo.
python scanner.py --bearish --top 30 --min-score 40
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
echo  BEARISH SCAN COMPLETE
pause
goto MENU

:TEST_MODE
cls
echo  === QUICK TEST - 50 stocks only (fast) ===
echo.
python scanner.py --test --top 10 --min-score 30
if errorlevel 1 echo  Test failed. & pause & goto MENU
echo.
echo  TEST COMPLETE
pause
goto MENU

:TIMEFRAME_SCAN
cls
echo  === SCAN BY TIMEFRAME ===
echo  daily   - Day-level patterns (Double Bottom, Wedge, etc.)
echo  weekly  - Week-level patterns (C&H Weekly)
echo  monthly - Month-level patterns (C&H Monthly)
echo.
set /p tfchoice="  Enter timeframe [daily/weekly/monthly]: "
if "%tfchoice%"=="" goto MENU
python scanner.py --top 30 --min-score 50 --timeframe %tfchoice%
if errorlevel 1 echo  Scanner failed. & pause & goto MENU
echo.
python gen_charts.py
start "" "results"
echo  SCAN COMPLETE
pause
goto MENU

:BACKTEST_COMPARE
cls
echo  === BACKTEST v3.1 vs v2 (backbone50, in-sample, ~5 min) ===
echo.
set /p btconfirm="  Start? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
python compare_backtest.py --stocks backbone50.txt --years 2 --min-score 40
echo  Results: results\backtest_v3.csv, results\backtest_v2.csv
pause
goto MENU

:BACKTEST_NIFTY200
cls
echo  === BACKTEST v3.1 vs v2 (nifty200, out-of-sample, ~15 min) ===
echo.
set /p btconfirm="  Start? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
python compare_backtest.py --stocks nifty200.txt --years 2 --min-score 40
echo  Results: results\backtest_v3.csv, results\backtest_v2.csv
pause
goto MENU

:BACKTEST_V3
cls
echo  === BACKTEST v3.1 only (backbone50, ~3 min) ===
echo  (Includes re-entry logic + 2.0x ATR + 8% stop cap)
echo.
set /p btconfirm="  Start? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
python backtest.py --stocks backbone50.txt --years 2 --min-score 40 --output results/backtest_v3_only.csv
echo  Results: results\backtest_v3_only.csv
pause
goto MENU

:SWEEP_ATR
cls
echo  === ATR MULTIPLIER SWEEP (backbone50, ~5 min) ===
echo  Tests 1.0x, 1.5x, 2.0x, 2.5x, 3.0x + no-cap to find optimal stop
echo.
set /p btconfirm="  Start? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
python sweep_atr.py
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
echo  (Merges new scan picks into existing tracker without losing ongoing trades)
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

:WHIPSAW
cls
echo  === WHIPSAW ANALYSIS ===
echo  Finds SL exits that would have hit target if held.
echo  Uses latest backtest_v3.csv results.
echo  Takes ~5-10 min (re-fetches price data for each SL exit).
echo.
set /p btconfirm="  Start? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
python whipsaw_analysis.py
pause
goto MENU

:RANK_2WEEK
cls
echo  === RANK TODAY'S PICKS BY 2-WEEK POTENTIAL ===
echo  Uses backtest stats to rank latest scan picks.
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

:ENHANCED_SCAN
cls
echo  === ENHANCED SCAN (full 15-pattern + pct_done/left + flags) ===
echo  Runs full v3.1 engine on backbone50 + nifty200 (~5 min)
echo  New: pct_done/left, [S] Sustained, [N] Nested cup, [D] Double confirm
echo  Upside filter: skips picks with less than 10pct left to T2
echo  Telegram sent automatically.
echo.
python _daily_scan_enhanced.py
pause
goto MENU

:TRACKER_STATUS
cls
echo  === TRACKER STATUS + TELEGRAM ===
echo  Shows open trades, waiting breakouts, wins, losses.
echo  Sends formatted status to Telegram.
echo.
python _tracker_status.py
pause
goto MENU

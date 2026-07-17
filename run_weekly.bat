@echo off
title Scanner v3 - Weekly Scan
cd /d "%~dp0"
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:MENU
cls
echo.
echo  ================================================================
echo                   SWING SCANNER v3 - WEEKLY
echo  ================================================================
echo.
echo   1.  Full scan (all NSE stocks, top 30)
echo   2.  Full scan + price filter (100-400 Rs)
echo   3.  Full scan + custom price range
echo   4.  Full scan + bearish mode (short setups)
echo   5.  Quick test (50 stocks only)
echo   6.  Scan by timeframe (daily / weekly / monthly only)
echo   7.  Backtest v3 vs v2 comparison (backbone50, in-sample)
echo   8.  Backtest v3 vs v2 comparison (nifty200, out-of-sample)
echo   9.  Backtest v3 only
echo  10.  Paper tracker - update prices + show status
echo  11.  Paper tracker - initialize from latest scan
echo  12.  Exit
echo.
set /p choice="  Enter choice [1-12]: "

if "%choice%"=="1" goto FULL_SCAN
if "%choice%"=="2" goto PRICE_FILTER
if "%choice%"=="3" goto CUSTOM_PRICE
if "%choice%"=="4" goto BEARISH
if "%choice%"=="5" goto TEST_MODE
if "%choice%"=="6" goto TIMEFRAME_SCAN
if "%choice%"=="7" goto BACKTEST_COMPARE
if "%choice%"=="8" goto BACKTEST_NIFTY200
if "%choice%"=="9" goto BACKTEST_V3
if "%choice%"=="10" goto PAPER_UPDATE
if "%choice%"=="11" goto PAPER_INIT
if "%choice%"=="12" exit /b 0
echo  Invalid choice.
pause
goto MENU

:FULL_SCAN
cls
echo.
echo  ================================================================
echo    FULL SCAN - All NSE stocks, top 30 setups
echo  ================================================================
echo.
echo  [1/4] Running scanner...
python scanner.py --top 30 --min-score 50
if errorlevel 1 (
    echo.
    echo  Scanner failed. Check errors above.
    pause
    goto MENU
)
echo.
echo  [2/4] Generating charts for top picks...
python gen_charts.py
if errorlevel 1 echo  Chart generation failed (non-critical).
echo.
echo  [3/4] Telegram notification sent automatically by scanner.
echo.
echo  [4/4] Opening results folder...
start "" "results"
echo.
echo  ================================================================
echo    SCAN COMPLETE - Results saved to results\ folder
echo  ================================================================
echo.
pause
goto MENU

:PRICE_FILTER
cls
echo.
echo  ================================================================
echo    FULL SCAN - Price filter 100-400 Rs (retail-friendly)
echo  ================================================================
echo.
echo  [1/4] Running scanner with price filter...
python scanner.py --top 30 --min-score 50 --min-price 100 --max-price 400
if errorlevel 1 (
    echo.
    echo  Scanner failed. Check errors above.
    pause
    goto MENU
)
echo.
echo  [2/4] Generating charts for top picks...
python gen_charts.py
if errorlevel 1 echo  Chart generation failed (non-critical).
echo.
echo  [3/4] Telegram notification sent automatically by scanner.
echo.
echo  [4/4] Opening results folder...
start "" "results"
echo.
echo  ================================================================
echo    SCAN COMPLETE - Results saved to results\ folder
echo  ================================================================
echo.
pause
goto MENU

:CUSTOM_PRICE
cls
echo.
echo  ================================================================
echo    FULL SCAN - Custom Price Range
echo  ================================================================
echo.
set /p minprice="  Enter minimum price (or press Enter for no limit): "
set /p maxprice="  Enter maximum price (or press Enter for no limit): "
echo.
set PRICE_ARGS=
if "%minprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --min-price %minprice%
if "%maxprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --max-price %maxprice%
echo  [1/4] Running scanner with price filter...
python scanner.py --top 30 --min-score 50 %PRICE_ARGS%
if errorlevel 1 (
    echo.
    echo  Scanner failed. Check errors above.
    pause
    goto MENU
)
echo.
echo  [2/4] Generating charts for top picks...
python gen_charts.py
if errorlevel 1 echo  Chart generation failed (non-critical).
echo.
echo  [3/4] Telegram notification sent automatically by scanner.
echo.
echo  [4/4] Opening results folder...
start "" "results"
echo.
echo  ================================================================
echo    SCAN COMPLETE - Results saved to results\ folder
echo  ================================================================
echo.
pause
goto MENU

:BEARISH
cls
echo.
echo  ================================================================
echo    BEARISH SCAN - Short setups in weak sectors
echo  ================================================================
echo.
echo  This finds stocks in the weakest NSE sectors with the most
echo  selling pressure. Looks for breakdown candidates.
echo.
echo  Running bearish scanner...
python scanner.py --bearish --top 30 --min-score 40
if errorlevel 1 (
    echo.
    echo  Scanner failed. Check errors above.
    pause
    goto MENU
)
echo.
echo  ================================================================
echo    BEARISH SCAN COMPLETE
echo  ================================================================
echo.
pause
goto MENU

:TEST_MODE
cls
echo.
echo  ================================================================
echo    QUICK TEST - 50 stocks only (fast)
echo  ================================================================
echo.
python scanner.py --test --top 10 --min-score 30
if errorlevel 1 (
    echo.
    echo  Test failed. Check errors above.
    pause
    goto MENU
)
echo.
echo  ================================================================
echo    TEST COMPLETE
echo  ================================================================
echo.
pause
goto MENU

:TIMEFRAME_SCAN
cls
echo.
echo  ================================================================
echo    SCAN BY TIMEFRAME
echo  ================================================================
echo.
echo  Filter patterns by timeframe. Useful for manual verification:
echo    daily   - Day-level patterns (Double Bottom, Wedge, Triangle, etc.)
echo    weekly  - Week-level patterns (C&H Weekly only currently)
echo    monthly - Month-level patterns (C&H Monthly only currently)
echo.
echo  Each result will show the timeframe so you can verify on charts.
echo.
set /p tfchoice="  Enter timeframe [daily/weekly/monthly]: "
if "%tfchoice%"=="" goto MENU
echo.
echo  [1/4] Running scanner with --timeframe %tfchoice%...
python scanner.py --top 30 --min-score 50 --timeframe %tfchoice%
if errorlevel 1 (
    echo.
    echo  Scanner failed. Check errors above.
    pause
    goto MENU
)
echo.
echo  [2/4] Generating charts for top picks...
python gen_charts.py
if errorlevel 1 echo  Chart generation failed (non-critical).
echo.
echo  [3/4] Telegram notification sent automatically by scanner.
echo.
echo  [4/4] Opening results folder...
start "" "results"
echo.
echo  ================================================================
echo    SCAN COMPLETE - Results saved to results\ folder
echo  ================================================================
echo.
pause
goto MENU

:BACKTEST_COMPARE
cls
echo.
echo  ================================================================
echo    BACKTEST - v3 vs v2 Comparison (Backbone50, In-Sample)
echo  ================================================================
echo.
echo  Runs walk-forward backtest on backbone50 stocks (2 years).
echo  Compares ATR stops + trailing (v3) vs original stops (v2).
echo  This takes about 5-10 minutes.
echo.
set /p btconfirm="  Start backtest? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
echo.
python compare_backtest.py --stocks backbone50.txt --years 2 --min-score 40
echo.
echo  Results saved to: results\backtest_v3.csv and results\backtest_v2.csv
echo.
pause
goto MENU

:BACKTEST_NIFTY200
cls
echo.
echo  ================================================================
echo    BACKTEST - v3 vs v2 Comparison (Nifty 200, Out-of-Sample)
echo  ================================================================
echo.
echo  Runs walk-forward backtest on nifty200 stocks (2 years).
echo  This is the OUT-OF-SAMPLE test -- validates that fixes
echo  generalize beyond the backbone50 in-sample dataset.
echo  Takes about 15-25 minutes (200 stocks x 2 modes).
echo.
set /p btconfirm="  Start backtest? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
echo.
python compare_backtest.py --stocks nifty200.txt --years 2 --min-score 40
echo.
echo  Results saved to: results\backtest_v3.csv and results\backtest_v2.csv
echo.
pause
goto MENU

:BACKTEST_V3
cls
echo.
echo  ================================================================
echo    BACKTEST - v3 Only
echo  ================================================================
echo.
echo  Runs walk-forward backtest on backbone50 stocks (2 years).
echo  Uses ATR stops + trailing stop after T1.
echo  This takes about 3-5 minutes.
echo.
set /p btconfirm="  Start backtest? [y/n]: "
if /i not "%btconfirm%"=="y" goto MENU
echo.
python backtest.py --stocks backbone50.txt --years 2 --min-score 40 --output results/backtest_v3_only.csv
echo.
echo  Results saved to: results\backtest_v3_only.csv
echo.
pause
goto MENU

:PAPER_UPDATE
cls
echo.
echo  ================================================================
echo    PAPER TRACKER - Update Prices + Show Status
echo  ================================================================
echo.
echo  Fetches current prices for all open paper trades and shows
echo  full status (open trades, closed trades, win rate, expectancy).
echo.
python paper_tracker.py update
echo.
python paper_tracker.py status
echo.
pause
goto MENU

:PAPER_INIT
cls
echo.
echo  ================================================================
echo    PAPER TRACKER - Initialize from Latest Scan
echo  ================================================================
echo.
echo  Creates a new paper tracker from the latest scan results CSV.
echo  This will REPLACE any existing tracker.
echo.
set /p ptconfirm="  Initialize tracker? This replaces existing data. [y/n]: "
if /i not "%ptconfirm%"=="y" goto MENU
echo.
python paper_tracker.py init
echo.
pause
goto MENU

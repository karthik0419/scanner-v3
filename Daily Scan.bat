@echo off
title Scanner v3 - Daily Scan
cd /d "%~dp0"
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:MENU
cls
echo.
echo  ================================================================
echo                   SCANNER v3 - DAILY MORNING
echo  ================================================================
echo.
echo   1.  Daily scan (auto-detect hot sectors, top 15)
echo   2.  Daily scan + price filter (100-400 Rs)
echo   3.  Daily scan + custom price range
echo   4.  Daily scan + custom sector
echo   5.  Daily bearish scan (weak sectors + short candidates)
echo   6.  Sector rotation heatmap only
echo   7.  Exit
echo.
set /p choice="  Enter choice [1-7]: "

if "%choice%"=="1" goto DAILY_DEFAULT
if "%choice%"=="2" goto DAILY_PRICE
if "%choice%"=="3" goto DAILY_CUSTOM_PRICE
if "%choice%"=="4" goto DAILY_SECTOR
if "%choice%"=="5" goto DAILY_BEARISH
if "%choice%"=="6" goto SECTOR_HEAT
if "%choice%"=="7" exit /b 0
echo  Invalid choice.
pause
goto MENU

:DAILY_DEFAULT
cls
echo.
echo  ================================================================
echo    DAILY SCAN - Auto-detect hot sectors, top 15
echo  ================================================================
echo.
python daily_scan.py --top 15
echo.
pause
goto MENU

:DAILY_PRICE
cls
echo.
echo  ================================================================
echo    DAILY SCAN - Price filter 100-400 Rs
echo  ================================================================
echo.
python daily_scan.py --top 15 --min-price 100 --max-price 400
echo.
pause
goto MENU

:DAILY_CUSTOM_PRICE
cls
echo.
echo  ================================================================
echo    DAILY SCAN - Custom Price Range
echo  ================================================================
echo.
set /p minprice="  Enter minimum price (or press Enter for no limit): "
set /p maxprice="  Enter maximum price (or press Enter for no limit): "
echo.
set PRICE_ARGS=
if "%minprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --min-price %minprice%
if "%maxprice%" neq "" set PRICE_ARGS=%PRICE_ARGS% --max-price %maxprice%
python daily_scan.py --top 15 %PRICE_ARGS%
echo.
pause
goto MENU

:DAILY_SECTOR
cls
echo.
echo  ================================================================
echo    DAILY SCAN - Custom Sector
echo  ================================================================
echo.
echo  Available sectors: METAL AUTO BANK IT PHARMA FMCG
echo                     ENERGY INFRA REALTY MEDIA PSU
echo.
set /p sector="  Enter sector name: "
echo.
set /p topn="  Show top N stocks [default 15]: "
if "%topn%"=="" set topn=15
python daily_scan.py --sector %sector% --top %topn%
echo.
pause
goto MENU

:DAILY_BEARISH
cls
echo.
echo  ================================================================
echo    DAILY BEARISH SCAN - Weak sectors + short candidates
echo  ================================================================
echo.
echo  Finds the weakest NSE sectors (most selling pressure)
echo  and flags stocks with biggest drops + volume surges.
echo.
python daily_scan.py --bearish --top 15
echo.
pause
goto MENU

:SECTOR_HEAT
cls
echo.
echo  ================================================================
echo    SECTOR ROTATION HEATMAP
echo  ================================================================
echo.
python -c "from utils.sector_rotation_v3 import print_sector_heatmap, get_weak_sectors; print_sector_heatmap(); print(); print('  Weak sectors (for bearish scans):'); [print(f'    {s:<16} 5d={p5:+.2f}%%  20d={p20:+.2f}%%') for s,p5,p20 in get_weak_sectors()]"
echo.
pause
goto MENU

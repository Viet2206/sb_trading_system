@echo off
setlocal EnableExtensions

set "PROJECT_ROOT=%~dp0.."
for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%" || exit /b 1

set "START_POLLER=1"
if /I "%~1"=="--no-poller" set "START_POLLER=0"

echo.
echo === SB Trading System: pull latest code ===
git pull --ff-only
if errorlevel 1 (
    echo.
    echo Git pull failed. Resolve git status first, then run this script again.
    pause
    exit /b 1
)

echo.
echo === Prepare environment files ===
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo Created .env from .env.example
)
findstr /B /C:"SB_DATA_SOURCE=" ".env" >nul || echo SB_DATA_SOURCE=ctrader>>".env"
findstr /B /C:"SB_API_HOST=" ".env" >nul || echo SB_API_HOST=0.0.0.0>>".env"
findstr /B /C:"SB_API_PORT=" ".env" >nul || echo SB_API_PORT=8010>>".env"
findstr /B /C:"SB_HISTORY_MONTHS=" ".env" >nul || echo SB_HISTORY_MONTHS=3>>".env"

set "DATA_SOURCE=ctrader"
for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"SB_DATA_SOURCE=" ".env"') do set "DATA_SOURCE=%%B"
set "REQUIREMENTS=requirements-ctrader.txt"
set "POLLER_TITLE=SB cTrader Poller"
set "POLLER_COMMAND=python scripts\poll_ctrader_to_files.py"
if /I "%DATA_SOURCE%"=="mt5" (
    set "REQUIREMENTS=requirements-win-mt5.txt"
    set "POLLER_TITLE=SB MT5 Poller"
    set "POLLER_COMMAND=python scripts\poll_mt5_to_files.py"
)

echo.
echo === Prepare Python virtual environment ===
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo Python virtual environment creation failed. Install Python and add it to PATH.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r "%REQUIREMENTS%"
if errorlevel 1 (
    echo Python dependency install failed.
    pause
    exit /b 1
)

echo.
echo === Prepare SB research index ===
python scripts\index_research_library.py
if errorlevel 1 (
    echo Research indexing failed. Review the PDF errors above and run this script again.
    pause
    exit /b 1
)

echo.
echo === Prepare fast market summary ===
if not exist "data\market\.candle-summary.json" (
    python scripts\rebuild_market_summary.py
    if errorlevel 1 (
        echo Market summary indexing failed. Stop the poller, repair any incomplete candle files, then retry.
        pause
        exit /b 1
    )
)

echo.
echo === Prepare Web UI dependencies ===
where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js/npm was not found. Install Node.js LTS and make sure it is added to PATH.
    echo Download: https://nodejs.org/
    pause
    exit /b 1
)

pushd "web"
call npm install
if errorlevel 1 (
    popd
    echo Web dependency install failed.
    pause
    exit /b 1
)
popd

echo.
echo === Start platform windows ===
if "%START_POLLER%"=="1" (
    start "%POLLER_TITLE%" /D "%PROJECT_ROOT%" cmd /k "call .venv\Scripts\activate.bat && %POLLER_COMMAND%"
) else (
    echo Skipping market data poller because --no-poller was passed.
)
start "SB API 8010" /D "%PROJECT_ROOT%" cmd /k "call .venv\Scripts\activate.bat && python scripts\run_api.py"
start "SB Web 5173" /D "%PROJECT_ROOT%\web" cmd /k "npm run dev"

echo.
echo Local URL:
echo   http://127.0.0.1:5173

where tailscale >nul 2>nul
if not errorlevel 1 (
    echo.
    echo Tailscale URL for Mac:
    for /f "usebackq tokens=*" %%I in (`tailscale ip -4`) do echo   http://%%I:5173
)

echo.
echo Started. Keep the new command windows open while using the platform.
pause

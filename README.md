# SB Trading System

SB Trading System is a Forex trading research and signal platform based on Stacey Burke trading concepts.

Same thing every week, over and over again.

The current development focus is Phase 1:

- Normalize the project direction.
- Prepare source documents for later strategy extraction.
- Build the first lightweight MT5-to-file market data ingestion path.
- Keep signal detection separate from future auto-trading.

## Local Setup

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy environment settings:

```bash
cp .env.example .env
```

The default setup now uses local file storage, so Docker and PostgreSQL are not required for the lightweight Windows workflow:

```env
SB_STORAGE=file
SB_DATA_DIR=data/market
SB_FILE_FORMAT=csv.gz
SB_UPDATE_INTERVAL_MINUTES=5
```

Run the backend API:

```bash
source .venv/bin/activate
python scripts/run_api.py --reload
```

Run the web UI:

```bash
cd web
pnpm install
pnpm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Windows No-Database MT5 Workflow

This is the recommended path for a small Windows laptop.

Install Python dependencies:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-win-mt5.txt
```

Copy environment settings:

```bat
copy .env.example .env
```

Open MetaTrader 5, log in to your broker account, then run one backfill/update cycle:

```bat
.venv\Scripts\activate
python scripts\poll_mt5_to_files.py --once
```

Run continuous 5-minute polling:

```bat
python scripts\poll_mt5_to_files.py
```

You can change the update interval from the Web UI Setting page. The API writes the interval to:

```text
data\runtime\settings.json
```

The polling script reads that file between update cycles.

If you already have exported CSV/CSV.gz files, import them into the active file store:

```bat
python scripts\import_candles_to_files.py data\raw\mt5_export
```

Then start the API and web UI in separate PowerShell windows:

```bat
.venv\Scripts\activate
python scripts\run_api.py --reload
```

```bat
cd web
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Tailscale Access From Mac

Run MT5, the poller, the API, and the web UI on the Windows laptop. Then open the web UI from your Mac through the Windows laptop's Tailscale address.

Install and log in to Tailscale on both Windows and Mac, then find the Windows Tailscale IP:

```bat
tailscale ip -4
```

In Windows `.env`, make sure the API host is not locked to localhost:

```env
SB_API_HOST=0.0.0.0
SB_API_PORT=8010
```

Start the API on Windows:

```bat
.venv\Scripts\activate
python scripts\run_api.py --reload
```

Start the web UI on Windows:

```bat
cd web
npm install
npm run dev
```

From your Mac, open:

```text
http://<WINDOWS_TAILSCALE_IP>:5173
```

For example:

```text
http://100.x.y.z:5173
```

The web UI automatically calls the backend API on the same Windows Tailscale host using port `8010`.

## Optional PostgreSQL Setup

Use this later for VPS, automation, trade logs, or larger workflows. Set `SB_STORAGE=postgres` in `.env`.

Start PostgreSQL with Docker:

```bash
docker compose up -d postgres
```

The default `.env.example` connection string already matches this local Docker database:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/sb_system
```

Check the database container:

```bash
docker compose ps
```

Run the Mac import notebook:

```bash
jupyter lab notebooks/02_mac_import_csv_to_postgres.ipynb
```

If the notebook shows `connection refused` on port `5432`, PostgreSQL is not running yet. Start it with `docker compose up -d postgres`, then rerun the connection/schema cell.

## MT5 Notes

The normal MT5 Python package workflow is intended to run on Windows with an installed MetaTrader 5 terminal. The recommended early workflow is:

- Windows laptop/VPS: connect to MT5 and write candles into local files under `data/market`.
- MacBook: use copied `data/market` files for development, or use PostgreSQL if desired.

This means Windows does not need Docker or PostgreSQL during early development.

Install the Windows/VPS dependencies with:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-win-mt5.txt
```

Register the project virtual environment as a Jupyter kernel:

```bat
python -m ipykernel install --user --name sb-system --display-name "SB Trading System (.venv)"
```

Then open Jupyter Lab and select the `SB Trading System (.venv)` kernel:

```bat
jupyter lab notebooks/01_windows_mt5_export.ipynb
```

If the notebook says `No module named 'MetaTrader5'`, the selected Jupyter kernel is not the same Python environment where the package was installed. Inside the notebook, run:

```python
import sys
print(sys.executable)
```

Then install into that exact interpreter:

```python
import sys
!"{sys.executable}" -m pip install -r requirements-win-mt5.txt
```

Restart the kernel after installation.

You can also verify the Windows MT5 environment from the terminal:

```bat
.venv\Scripts\activate
python scripts\check_mt5_env.py
```

## Offline MT5 Data Workflow

If `.env` was copied before broker symbols were updated, edit it manually before export:

```env
SB_SYMBOLS=EURUSD,GBPUSD,USDJPY,AUDUSD,NZDUSD,USDCAD,AMD,MSFT,XAUUSD.pc,NAS100,BTCUSD.sc,USDCHF.pc,GBPJPY.pc,EURJPY.pc,SP500,AUDCAD.pc,AUDCHF.pc,AUDJPY.pc,CADCHF.pc,CADJPY.pc,CHFJPY.pc,COPPER-C,EURAUD.pc,EURCAD.pc,EURCHF.pc,EURGBP.pc,GBPAUD.pc,GBPCAD.pc,GBPCHF.pc
```

Use the exact broker symbols shown in MetaTrader 5 Market Watch, including suffixes like `.pc` and `.sc`.

On Windows, export MT5 candles into local files:

```bat
git pull
.venv\Scripts\activate
python scripts\export_mt5_candles.py --output-dir data\raw\mt5_export
```

Or use the Windows notebook:

```bat
jupyter lab notebooks\01_windows_mt5_export.ipynb
```

This creates files like:

```text
data\raw\mt5_export\EURUSD_M15_2026-01-01_to_now.csv.gz
data\raw\mt5_export\manifest.json
```

Move the `data\raw\mt5_export` folder from Windows to the MacBook if you want to test there.

On MacBook, import the exported files into local file storage:

```bash
git pull
source .venv/bin/activate
python scripts/import_candles_to_files.py data/raw/mt5_export
```

Optional Postgres import is still available:

```bash
docker compose up -d postgres
python scripts/import_candles_from_csv.py data/raw/mt5_export
```

After import, continue building and testing SB Trading System features on Mac or Windows.

## Backend API

After candles are written to `data/market` or imported from CSV exports, start the backend API:

```bash
source .venv/bin/activate
python scripts/run_api.py --reload
```

Open the interactive API docs:

```text
http://127.0.0.1:8010/docs
```

Useful endpoints:

```text
GET /health
GET /symbols
GET /candles/summary
GET /candles?symbol=EURUSD&timeframe=M15&limit=200
GET /context/overlays?symbol=EURUSD&timeframe=M15&limit=1500
GET /runtime/settings
PUT /runtime/settings
```

The `/context/overlays` endpoint returns the first SB context layer for the active chart: previous day high/low, previous week high/low, latest Friday close, current Monday high/low, chart day periods, intraday previous-day-close segments, Asia/London/New York session boxes, weekday labels, and deterministic daily setup labels for Inside Day, FGD, FRD, 3DL, and 3DS. FGD requires a green daily candle after at least two consecutive red daily candles, FRD requires a red daily candle after at least two consecutive green daily candles, and 3DL/3DS marks only the third consecutive green/red daily candle. Current session windows use chart/data time: Asia 03:00-06:00, London 09:00-12:00, New York 15:00-18:00. Intraday day-period and session templates are hidden on H4 and D1 charts. Horizontal context levels are light blue, intraday previous-day-close segments are green, previous-day high/low pipes are gray dashed step lines, and session boxes are separated by fill color without text labels by default; these colors and styles can be changed on the Web UI Settings page.

## Web UI

Start the React chart dashboard after the backend API is running:

```bash
cd web
pnpm install
pnpm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The first dashboard supports:

- Sidebar navigation for Chart, Daily Checklist, and Setting
- Symbol/timeframe selection and refresh from the chart header
- Interactive candlestick chart with pan, zoom, and crosshair
- Black and white candlestick styling
- SB context overlays for solid right-extending key level rays, intraday previous-day high/low pipes, intraday day periods, month/day separators, color-separated session boxes, weekday labels, and v0 daily setup labels
- Default visible chart view: latest 7 days for M1/M5/M15/M30/H1 and latest 30 days for H4/D1. Data is still loaded from the full available imported history.
- Settings page controls the update interval used by chart auto-refresh and the Windows MT5 polling script.

## Project Instructions

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for the durable architecture and development plan.

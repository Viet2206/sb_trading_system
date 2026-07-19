# SB System

SB System is a Forex trading research and signal platform based on Stacey Burke trading concepts.

The current development focus is Phase 1:

- Normalize the project direction.
- Prepare source documents for later strategy extraction.
- Build the first MT5-to-Postgres market data ingestion path.
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

- Windows laptop/VPS: connect to MT5 and export candles to compressed CSV files.
- MacBook: import those CSV files into local Docker PostgreSQL and build platform features.

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
python -m ipykernel install --user --name sb-system --display-name "SB System (.venv)"
```

Then open Jupyter Lab and select the `SB System (.venv)` kernel:

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

Move the `data\raw\mt5_export` folder from Windows to the MacBook.

On MacBook, start local Postgres and import the exported files:

```bash
git pull
docker compose up -d postgres
source .venv/bin/activate
python scripts/import_candles_from_csv.py data/raw/mt5_export
```

Or use the Mac notebook:

```bash
jupyter lab notebooks/02_mac_import_csv_to_postgres.ipynb
```

After import, continue building and testing SB System features on Mac using local PostgreSQL.

## Backend API

After candles are imported into local PostgreSQL, start the backend API:

```bash
source .venv/bin/activate
python scripts/run_api.py --reload
```

Open the interactive API docs:

```text
http://127.0.0.1:8000/docs
```

Useful endpoints:

```text
GET /health
GET /symbols
GET /candles/summary
GET /candles?symbol=EURUSD&timeframe=M15&limit=200
GET /context/overlays?symbol=EURUSD&timeframe=M15&limit=1500
```

The `/context/overlays` endpoint returns the first SB context layer for the active chart: previous day high/low, previous week high/low, latest Friday close, current Monday high/low, chart day periods, intraday previous-day-close segments, Asia/London/New York session boxes, weekday labels, and v0 setup labels for Inside Day, FGD, FRD, 3DL, and 3DS. Current session windows use chart/data time: Asia 03:00-06:00, London 09:00-12:00, New York 15:00-18:00. Intraday day-period and session templates are hidden on H4 and D1 charts. Overlay linework is neutral gray by default so the black/white candles remain the strongest visual signal.

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

- Symbol and timeframe selection
- Interactive candlestick chart with pan, zoom, and crosshair
- Black and white candlestick styling
- SB context overlays for solid right-extending key level rays, intraday previous-day high/low pipes, intraday day periods, month/day separators, session boxes, weekday labels, and v0 daily setup labels
- Default visible chart view: latest 7 days for M1/M5/M15/M30/H1 and latest 30 days for H4/D1. Data is still loaded from the full available imported history.

## Project Instructions

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for the durable architecture and development plan.

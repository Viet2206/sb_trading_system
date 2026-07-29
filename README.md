# SB Trading System

SB Trading System is a Forex trading research and signal platform based on Stacey Burke trading concepts.

Same thing every week, over and over again.

The current development focus is a complete non-trading research workflow:

- Five-minute cTrader candle collection with local file storage.
- Deterministic, provisional SB context and signal labels.
- Searchable PDF playbook and chart-example library.
- Evidence-backed RAG and AI analysis with source-page citations.
- Visual PDF-page inspection and optional AI vision analysis.
- Human validation through Chart, Daily Checklist, and Research workspaces.

Trading execution and risk automation remain out of scope until the signal rules are
validated against labelled examples.

Native chart versions of the current `weekly_template` are available for
[MetaTrader 5 and cTrader](indicators/README.md). They include the SB context,
session, previous-day pipe/close, CIB, and provisional daily-label layers, but
intentionally exclude the separate 5 EMA and Major Round Number templates.

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

Build or update the local research index:

```bash
python scripts/index_research_library.py
```

The local index supports search and RAG retrieval without an API key. To enable AI
synthesis and visual page analysis, configure either Z.AI or OpenAI in `.env`. Keep
credentials out of Git and do not enter them in the browser UI.

The default setup now uses local file storage, so Docker and PostgreSQL are not required for the lightweight Windows workflow:

```env
SB_STORAGE=file
SB_DATA_SOURCE=ctrader
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

## cTrader No-Database Workflow

This is the recommended path for 5-minute SB Strategy updates. cTrader Open API writes candles into `data/market`, and the existing API/UI reads those files.

Create a cTrader Open API application at:

```text
https://openapi.ctrader.com/
```

Then update `.env`:

```env
SB_DATA_SOURCE=ctrader
CTRADER_HOST_TYPE=demo
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_REDIRECT_URI=http://localhost
CTRADER_ACCESS_TOKEN=your_access_token
CTRADER_REFRESH_TOKEN=your_refresh_token
CTRADER_ACCOUNT_ID=your_account_id
CTRADER_SYMBOLS=EURUSD,GBPUSD,USDJPY,AUDUSD,XAUUSD,NAS100,SP500
CTRADER_TIMEFRAMES=M5,M15,H1,H4,D1
```

Generate the missing OAuth token and account ID:

```bat
python scripts\ctrader_auth_helper.py --print-url --write-env
```

Open the printed URL, approve access in cTrader, then copy the `code` value from the redirect URL and run:

```bat
python scripts\ctrader_auth_helper.py --code YOUR_AUTH_CODE --write-env
python scripts\ctrader_auth_helper.py --accounts --write-env
```

If cTrader returns multiple accounts, choose one:

```bat
python scripts\ctrader_auth_helper.py --accounts --account-id YOUR_ACCOUNT_ID --write-env
```

After installing Python, Node.js LTS, Git, and Tailscale, you can pull code and start the whole platform with one script:

```bat
scripts\windows_start_platform.bat
```

This script opens separate windows for:

- cTrader candle polling
- Backend API on port `8010`
- Web UI on port `5173`

It also installs the research dependencies and incrementally indexes the PDFs under
`docs` before the services start.

If you only want API + Web UI and do not want to poll broker data yet:

```bat
scripts\windows_start_platform.bat --no-poller
```

Install Python dependencies:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-ctrader.txt
```

Copy environment settings:

```bat
copy .env.example .env
```

Run one cTrader backfill/update cycle:

```bat
.venv\Scripts\activate
python scripts\poll_ctrader_to_files.py --once
```

Run continuous 5-minute polling:

```bat
python scripts\poll_ctrader_to_files.py
```

You can change the update interval from the Web UI Setting page. The API writes the interval to:

```text
data\runtime\settings.json
```

The cTrader polling script reads that file between update cycles.

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

Run the cTrader poller, the API, and the web UI on the host machine. Then open the web UI from your Mac through the host machine's Tailscale address.

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

## Optional MT5 Workflow

MT5 support remains available if you later switch back to a Windows terminal workflow. Set this in `.env`:

```env
SB_DATA_SOURCE=mt5
```

Install MT5 dependencies:

```bat
python -m pip install -r requirements-win-mt5.txt
```

Run the MT5 poller:

```bat
python scripts\poll_mt5_to_files.py
```

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

## Legacy MT5 Notes

The MT5 Python package workflow is intended to run on Windows with an installed MetaTrader 5 terminal. Keep this only as a fallback workflow:

- Windows laptop/VPS: connect to MT5 and write candles into local files under `data/market`.
- MacBook: use copied `data/market` files for development, or use PostgreSQL if desired.

This means Windows does not need Docker or PostgreSQL if you use the MT5 fallback.

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

This legacy path is useful only if you still want to export from MetaTrader 5. If `.env` was copied before broker symbols were updated, edit it manually before export:

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
GET /research/status
POST /research/index
GET /research/documents
GET /research/search?query=first+green+day
GET /research/image-matches/status
POST /research/image-matches/index
POST /research/image-matches
GET /research/chart-images/{example_id}
POST /research/analyze
POST /research/vision
```

The `/context/overlays` endpoint returns the first SB context layer for the active chart: previous day high/low, previous week high/low, latest Friday close, current Monday high/low, chart day periods, intraday previous-day-close segments, Asia/London/New York session boxes, weekday labels, and deterministic daily setup labels for Inside Day, FGD, FRD, CIB, 2CIB, 3DL, and 3DS. CIB requires the daily close to finish above the prior high or below the prior low, and 2CIB requires consecutive closing-breakout days. FGD requires a green daily candle after at least two consecutive red daily candles, FRD requires a red daily candle after at least two consecutive green daily candles, and 3DL/3DS marks only the third consecutive green/red daily candle. Current session windows use chart/data time: Asia 03:00-06:00, London 09:00-12:00, New York 15:00-18:00. Intraday day-period and session templates are hidden on H4 and D1 charts. Horizontal context levels are light blue, intraday previous-day-close segments are green, previous-day high/low pipes are gray dashed step lines, and session boxes are separated by fill color without text labels by default; these colors and styles can be changed on the Web UI Settings page.

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

The dashboard supports:

- Sidebar navigation for Chart, Daily Checklist, Research, and Setting
- Symbol/timeframe selection and refresh from the chart header
- Interactive candlestick chart with pan, zoom, and crosshair
- Black and white candlestick styling
- SB context overlays for solid right-extending key level rays, intraday previous-day high/low pipes, intraday day periods, month/day separators, color-separated session boxes, weekday labels, and v0 daily setup labels
- Default visible chart view: latest 7 days for M1/M5/M15/M30/H1 and latest 30 days for H4/D1. Data is still loaded from the full available imported history.
- Settings page controls the update interval used by chart auto-refresh and the cTrader polling script.
- Research Search combines local vector similarity, sparse term matching, setup filters,
  and page-level citations.
- Historical Image Matches captures the visible chart only when Search is pressed,
  compares its local visual vector with every extracted example chart, and returns
  the five highest cosine-similarity results. This path makes no LLM call.
- Example PDFs are chunked into individual chart images and indexed locally under
  `data/research`. Similarity is a visual retrieval score, not win probability.
- Research Library inventories every indexed document and opens the original PDF.
- Research Analyst combines deterministic market context with retrieved evidence. It
  operates in retrieval-only mode until a supported AI provider is configured.
- Source Inspector renders the original PDF page and optionally sends that page to the
  configured multimodal model for visual analysis.

## Research And AI

The repository currently contains 27 PDFs and 1,086 pages. Indexing creates a local
SQLite file under `data/research`; this generated index is deliberately excluded from
Git and is rebuilt on each machine.

Build the historical chart-image index:

```bash
python scripts/index_chart_images.py --rebuild
```

Default configuration:

```env
SB_RESEARCH_DOCS_DIR=docs
SB_RESEARCH_INDEX=data/research/research.sqlite3
SB_EMBEDDING_PROVIDER=local
SB_AI_PROVIDER=zai
ZAI_BASE_URL=https://api.z.ai/api/paas/v4
ZAI_MODEL=glm-4.7
ZAI_VISION_MODEL=glm-4.6v-flash
OPENAI_MODEL=gpt-5.6-terra
OPENAI_REASONING_EFFORT=low
```

Use `SB_EMBEDDING_PROVIDER=local` for the small Windows/VPS deployment. Optional OpenAI
embeddings can be enabled later with `SB_EMBEDDING_PROVIDER=openai`; rebuild the index
after changing providers:

```bash
python scripts/index_research_library.py --rebuild
```

See [Research AI Architecture](docs/RESEARCH_AI_ARCHITECTURE.md) for the data flow,
evidence contract, and validation boundary.

## Project Instructions

See [INSTRUCTIONS.md](INSTRUCTIONS.md) for the durable architecture and development plan.

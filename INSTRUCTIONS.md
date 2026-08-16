# SB Trading System - Project Instructions

## Project Vision

SB Trading System is a Forex trading research and signal platform based on Stacey Burke trading concepts.

Product bio: "Same thing every week, over and over again"

The first goal is to build a reliable signal and research system. Auto-trading is intentionally out of scope until the strategy rules, examples, backtesting, and paper-trading results are validated.

This project should stay testable, explainable, and evidence-driven. AI should help classify, compare, explain, and retrieve relevant historical examples. AI should not be the only source of trade decisions.

## Current Source Material

Strategy and example documents are stored under:

- `docs/strategy_note/`
- `docs/chart_template_notes/`

The PDF documents include Stacey Burke playbook notes, trade setup examples, session examples, opening range examples, inside day examples, first green day examples, first red day examples, pump and dump examples, parabolic examples, and other chart markup references.

Do not treat the PDFs as already-structured strategy rules. The first research task is to extract, normalize, and validate the concepts into a machine-readable strategy specification.

## Product Direction

Build SB Trading System as a web application with a backend service and a broker data bridge.

Preferred direction:

- Web UI usable from both Windows and macOS laptops.
- cTrader Open API is the preferred Phase 1 market-data source because it can run from Mac or Windows without a local MT5 terminal.
- MT5 remains an optional fallback for Windows/VPS.
- A bridge process connects broker data to the backend.
- Backend handles strategy logic, data storage, RAG, pattern search, and signal scoring.
- Web UI displays live charts, detected setups, overlays, similar examples, and confidence details.

Avoid building the first version as a Windows-only desktop app. That would make AI, RAG, visual search, testing, and cross-platform use harder.

Current lightweight deployment direction:

- MacBook or Windows laptop runs the cTrader Open API poller, the FastAPI backend, and the web UI.
- No Docker or database is required for the first deployment.
- A Python cTrader polling process writes candles into local files under `data/market`.
- The backend reads those local files directly when `SB_STORAGE=file`.
- The Settings page controls the shared update interval used by the UI auto-refresh and the cTrader polling process.
- PostgreSQL remains available later by switching `SB_STORAGE=postgres`.

## Core Principle

Separate the system into three layers:

1. Deterministic rule engine
2. AI-assisted explanation and comparison
3. Human decision workflow

The rule engine should generate setup candidates. AI should retrieve examples, compare similarity, and explain confidence. The user should confirm signals before any real trading.

## High-Level Architecture

```mermaid
flowchart LR
  Broker["cTrader Open API / Broker"]
  Bridge["Market Data Bridge"]
  Backend["Backend API"]
  Engine["SB Strategy Engine"]
  AI["AI Layer"]
  DB["Market + Trade Database"]
  Vector["Vector Store"]
  UI["Web UI"]
  Chart["Live Chart Overlay"]

  Broker --> Bridge --> Backend
  Backend --> Engine
  Backend --> AI
  Backend --> DB
  AI --> Vector
  Backend --> UI
  UI --> Chart
```

## Main Components

### 1. Market Data Bridge

Responsible for getting historical and 5-minute refreshed market data from the broker.

Possible implementations:

- cTrader Open API Python poller for trendbars.
- Python process using the MetaTrader5 package.
- MQL5 Expert Advisor sending data to the backend through WebRequest or sockets.
- Hybrid approach: Python for research/backtesting, MQL5 EA for production signal/execution bridge.

Initial scope:

- Read symbols, candles, ticks, spread, and account metadata.
- Save normalized candle data to the file store for the current no-database phase.
- Do not execute real trades in the first version.

Current implementation:

- Preferred script: `scripts/poll_ctrader_to_files.py`
- OAuth helper: `scripts/ctrader_auth_helper.py`
- Optional legacy MT5 script: `scripts/poll_mt5_to_files.py`
- First cTrader run backfills from `CTRADER_IMPORT_START`.
- Later runs re-request a small overlap before the latest saved candle so active/incomplete candles can be updated safely.
- Runtime update interval is stored in `data/runtime/settings.json` and can be changed from the Web UI Setting page.
- Required cTrader values are `CTRADER_CLIENT_ID`, `CTRADER_CLIENT_SECRET`, `CTRADER_ACCESS_TOKEN`, and `CTRADER_ACCOUNT_ID`.
- Use `python scripts\ctrader_auth_helper.py --print-url --write-env`, then `--code YOUR_AUTH_CODE --write-env`, then `--accounts --write-env` to obtain token/account values.

### 2. Backend API

Suggested stack:

- Python
- FastAPI
- PostgreSQL for durable storage
- SQLite is acceptable for early prototype
- Optional TimescaleDB later for larger candle/tick history

Responsibilities:

- Receive market data from cTrader or MT5 bridge.
- Store OHLCV/tick/session data.
- Run deterministic strategy detection.
- Serve signals and chart overlays to the UI.
- Manage pattern library metadata.
- Manage RAG and vector search.

Current storage modes:

- `SB_STORAGE=file`: read candles from `data/market/<symbol>/<timeframe>.csv.gz`; recommended for the small Windows laptop phase.
- `SB_STORAGE=postgres`: read candles from PostgreSQL; keep for VPS, automation, trade logs, and larger multi-process workflows.

### 3. SB Strategy Engine

This is the most important part of the system.

It should convert Stacey Burke concepts into explicit, testable rules. Each detected setup should include:

- Symbol
- Timeframe
- Session
- Setup type
- Price location
- Entry zone
- Stop area
- Target area
- Invalidation condition
- Rule match score
- Relevant historical examples
- Explanation

The strategy engine should be deterministic where possible. Do not hide core trade rules inside an LLM prompt.

### 4. Pattern Library

The existing chart example PDFs should become a searchable pattern library.

Each example should eventually have:

- Source PDF
- Page number
- Screenshot/image crop
- Symbol if known
- Timeframe if known
- Market session
- Setup type
- Direction
- Entry logic
- Stop logic
- Target logic
- Outcome if known
- Tags
- Notes

Suggested tags:

- first green day
- first red day
- pump and dump
- parabolic
- short squeeze
- inside day
- opening range
- three sessions
- breakout trader
- HOD/LOD
- major news first bounce
- low hanging fruit

### 5. RAG Pipeline

RAG should support explanation and evidence retrieval.

Pipeline:

1. Extract text and images from PDFs.
2. Split content by concept, setup, page, and example.
3. Store text chunks with metadata.
4. Store chart image embeddings separately from text embeddings where possible.
5. Retrieve relevant notes and examples for each detected setup.
6. Show citations back to the source PDF/page.

RAG output should answer:

- Which Stacey Burke concept does this setup resemble?
- Which historical examples are closest?
- What evidence supports the signal?
- What evidence weakens the signal?
- What should invalidate the setup?

Current implementation:

- `scripts/index_research_library.py` incrementally indexes all PDFs under `docs`.
- `src/sb_system/research.py` stores document, page, chunk, setup tag, and vector
  metadata in local SQLite under `data/research`.
- Search combines a deterministic local feature vector, sparse query overlap, setup
  aliases, and explicit setup filters.
- Every result retains document ID, title, category, page number, excerpt, and score.
- Source PDFs and rendered source pages are served by the backend for direct review.
- The generated index and page cache are local runtime data and must not be committed.

### 6. Computer Vision

Computer vision is useful for chart screenshot comparison and example retrieval, but it should not replace OHLC/time/session logic.

Recommended use:

- Extract chart regions from PDFs.
- Compare current chart image to historical examples.
- Rank visually similar examples.
- Detect approximate shapes such as W/M patterns, parabolic moves, opening range behavior, or HOD/LOD sweeps.

Risk:

- Chart images can vary by theme, zoom level, broker candle shape, indicators, and annotations.
- Prefer structured candle data for live rule detection.

Current implementation:

- PDF pages can be rendered on demand with PyMuPDF and inspected in the Research UI.
- When Z.AI or OpenAI is configured, the selected source page can be submitted as an
  image input for annotation and setup analysis.
- Vision output is supporting evidence only. It cannot create or override a
  deterministic signal.

### 7. Web UI

The web UI should be the main operator interface.

Important views:

- Live chart with SB overlays
- Active signal list
- Signal detail panel
- Similar historical examples
- RAG explanation with source references
- Pattern library browser
- Backtest/replay view
- Trade journal
- Settings for symbols, sessions, risk, and confidence thresholds

Chart overlay should support:

- Session boxes
- HOD/LOD marks
- Opening range
- Entry zone
- Stop zone
- Target zone
- Pattern labels
- Confidence breakdown

Current Phase 1 overlay implementation:

- Backend endpoint: `GET /context/overlays`
- First context levels: previous day high/low, previous week high/low, previous month high/low, current month first trading-day high/low, latest Friday close, and current Monday high/low as solid right-extending rays from their relevant start time
- First intraday range layer: previous-day high and low are drawn as gray dashed connected step pipes, high-to-high and low-to-low, across day periods; pipe corner radius is adjustable
- First day layer: custom chart day-period bands with centered weekday labels; avoid relying on the chart library's default grid
- First month layer: vertical month separators across the chart
- First intraday close layer: previous-day-close is drawn as a green horizontal segment that spans only the current day period
- First session layer: Asia 03:00-06:00, London 09:00-12:00, and New York 15:00-18:00 boxes using chart/data time; separate sessions by fill color and do not render session text labels on the chart
- Intraday day/session templates are hidden on H4 and D1 charts
- Default visible chart view is 7 days for M1/M5/M15/M30/H1 and 30 days for H4/D1; do not restrict the loaded candle history for this behavior
- First labels: weekday labels plus deterministic daily setup labels. Inside Day requires today's high/low inside the previous day range. FGD requires a green daily candle after at least two consecutive red daily candles. FRD requires a red daily candle after at least two consecutive green daily candles. 3DL/3DS marks only the third consecutive green/red daily candle, not every later continuation day.
- Sidebar navigation has Chart, Daily Checklist, Research, and Setting pages; symbol/timeframe/refresh controls live in the chart header
- Chart overlays are registered as independently toggleable templates. `weekly_template` contains the SB context overlay; `five_ema` contains native EMA 9, 21, 50, 100, and 200 series. Template selections persist in browser local storage.
- Web UI Setting page controls overlay colors, line styles, label colors, each session fill color, and right-side chart spacing, with values saved in browser local storage
- Web UI Setting page also controls the update interval in minutes; this is saved to the backend runtime settings file for the cTrader poller and used by the chart auto-refresh
- These labels are deterministic context markers and must be validated/refined against manually tagged Stacey Burke examples before they are treated as trading signals.

## Signal Confidence Model

Avoid one vague AI confidence score.

Use a transparent score made from multiple components:

- Rule match strength
- Session/time validity
- Location quality
- Market structure quality
- Pattern similarity
- Historical example similarity
- Spread/liquidity condition
- RAG evidence strength
- AI uncertainty or contradiction notes

Example structure:

```json
{
  "symbol": "EURUSD",
  "timeframe": "M15",
  "setup_type": "pump_and_dump",
  "direction": "short",
  "confidence": 0.78,
  "components": {
    "rule_match": 0.85,
    "session_validity": 0.9,
    "location_quality": 0.75,
    "pattern_similarity": 0.72,
    "rag_evidence": 0.8,
    "spread_condition": 0.7
  }
}
```

## Development Phases

### Phase 1 - Strategy Research and Rule Specification

Goal: turn PDFs and examples into a structured SB strategy specification.

Deliverables:

- Setup taxonomy
- Rule definitions
- Session definitions
- Pattern tags
- Invalidation rules
- Data requirements
- Initial scoring model

### Phase 2 - Document and Example Index

Goal: make source material searchable.

Deliverables:

- PDF inventory
- Extracted text
- Extracted chart images
- Metadata per PDF/page/example
- Initial vector index
- Simple retrieval script/API

### Phase 3 - Market Data Foundation

Goal: connect cTrader Open API and store normalized market data.

Deliverables:

- cTrader Open API bridge prototype
- Candle/tick schema
- Symbol/session configuration
- Historical import
- Data quality checks

### Phase 4 - Rule-Based Signal Engine

Goal: detect candidate setups using explicit rules.

Deliverables:

- Setup detectors
- Signal objects
- Confidence components
- Unit tests with sample data
- Backtest/replay support

### Phase 5 - Web UI Signal Dashboard

Goal: show signals clearly.

Deliverables:

- Live chart
- Overlay drawing
- Signal panel
- Similar examples panel
- Explanation panel
- Pattern library view

### Phase 6 - RAG and Visual Similarity

Goal: connect signals to source material and historical examples.

Deliverables:

- RAG search API
- PDF/page citations
- Similar example ranking
- Chart image similarity
- Confidence explanation

Implementation status:

- Complete: document inventory, text extraction, page citations, local hybrid search,
  source-page rendering, RAG evidence packets, retrieval-only fallback, AI synthesis,
  and optional visual source-page analysis.
- Pending validation data: calibrated visual similarity between the current chart and
  labelled historical examples. Page/title/setup retrieval is available now, but a
  meaningful image-similarity confidence score requires user-reviewed example labels.

### Phase 7 - Paper Trading and Validation

Goal: validate the system without real execution.

Deliverables:

- Paper trade tracking
- Signal outcome tracking
- Trade journal
- Performance reports
- False positive analysis

### Phase 8 - Optional Auto-Trading

Only consider this after enough validation.

Requirements before auto-trading:

- Stable signal engine
- Clear risk management
- Backtest results
- Forward paper-trading results
- Broker execution testing
- Fail-safe controls
- Manual override
- Full logging

## Suggested Technology Stack

Initial prototype:

- Backend: Python + FastAPI
- Database: SQLite first, PostgreSQL later
- Vector search: local vector DB first, upgrade later if needed
- Frontend: React or Next.js
- Charting: Lightweight Charts, TradingView library if available/licensed, or another robust financial chart component
- Market-data bridge: cTrader Open API first, MT5 Python package or MQL5 EA as fallback

Keep the first version simple. Prefer working signal detection and review flow over complex infrastructure.

## Data Model Concepts

Core entities:

- Symbol
- Candle
- Tick
- Session
- SetupPattern
- Signal
- SignalScore
- PatternExample
- SourceDocument
- DocumentChunk
- ChartImage
- TradeJournalEntry
- BacktestRun

## Early Engineering Rules

- Do not build auto-trading first.
- Do not make the LLM the trading engine.
- Do not hardcode broker-specific assumptions without config.
- Do not skip source metadata when extracting from PDFs.
- Do not lose page numbers, file names, or chart-example references.
- Do not optimize infrastructure before the rules are clear.
- Build small verifiable modules.
- Keep all strategy rules auditable.
- Every signal should explain why it exists and what would invalidate it.

## GitHub Workflow

For implementation tasks, finish with a GitHub-ready change set:

- Create a feature branch before editing files.
- Keep notebook execution output out of commits unless it is intentionally part of the deliverable.
- Commit only files related to the task.
- Push the branch to GitHub.
- Open a pull request into `main`.
- Include a short summary, verification notes, and any known limitations in the PR description.

## Open Questions To Resolve

- Signal labels remain provisional until tested by the user against known examples.
- The first markets are XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD, NAS100, and SP500.
- Timestamps remain UTC and the existing session windows remain unchanged.
- cTrader is the preferred five-minute source; file storage remains the default.
- AI explains and retrieves evidence. It does not invent signals or execute trades.
- Auto-trading and risk automation remain out of scope.

## First Implementation Target

The first useful milestone should be:

"Given historical candles and a small manually tagged pattern library, SB Trading System detects candidate setup zones on a chart and shows similar historical examples with an explanation."

This milestone avoids premature auto-trading and creates the foundation for testing the strategy properly.

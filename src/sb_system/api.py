from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.engine import Engine

from sb_system.ai_research import SBResearchAgent
from sb_system.chart_window import MAX_CHART_CANDLES, chart_window_start
from sb_system.context import build_sb_overlays
from sb_system.daily_checklist import build_daily_checklist, save_checklist_state
from sb_system.file_store import (
    fetch_file_candle_summary,
    fetch_file_candles,
    fetch_file_symbols,
)
from sb_system.market_data import (
    ImportConfig,
    check_connection,
    create_db_engine,
    create_schema,
    dataframe_records,
    fetch_candle_summary,
    fetch_candles,
    fetch_symbols,
    load_config,
)
from sb_system.runtime_settings import (
    RuntimeSettings,
    load_runtime_settings,
    runtime_settings_from_payload,
    save_runtime_settings,
)
from sb_system.telegram import TelegramNotifier
from sb_system.research import ResearchLibrary, SETUP_TAXONOMY


app = FastAPI(
    title="SB Trading System API",
    version="0.1.0",
    description="Research API for imported broker candle data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_origin_regex=(
        r"^https?://[A-Za-z0-9_.-]+:517[3-9]$"
        r"|^https?://(?:\d{1,3}\.){3}\d{1,3}:517[3-9]$"
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_config() -> ImportConfig:
    return load_config(require_database_url=False)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    config = get_config()
    if not config.database_url:
        raise RuntimeError("DATABASE_URL is required.")
    engine = create_db_engine(config.database_url)
    create_schema(engine)
    return engine


@lru_cache(maxsize=1)
def get_research_library() -> ResearchLibrary:
    return ResearchLibrary()


@lru_cache(maxsize=1)
def get_research_agent() -> SBResearchAgent:
    return SBResearchAgent(get_research_library())


@lru_cache(maxsize=1)
def get_telegram_notifier() -> TelegramNotifier:
    return TelegramNotifier()


@app.get("/health")
def health(config: Annotated[ImportConfig, Depends(get_config)]) -> dict:
    if config.storage == "file":
        return {
            "status": "ok",
            "storage": "file",
            "data_dir": str(config.data_dir),
            "file_format": config.file_format,
            "runtime_settings": _runtime_settings_payload(),
        }

    try:
        rows = dataframe_records(check_connection(get_engine()))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return {
        "status": "ok",
        "storage": "postgres",
        "database": rows[0] if rows else None,
        "runtime_settings": _runtime_settings_payload(),
    }


@app.get("/symbols")
def symbols(config: Annotated[ImportConfig, Depends(get_config)]) -> list[dict]:
    if config.storage == "file":
        return dataframe_records(fetch_file_symbols(config.data_dir, file_format=config.file_format))
    return dataframe_records(fetch_symbols(get_engine()))


@app.get("/candles/summary")
def candle_summary(config: Annotated[ImportConfig, Depends(get_config)]) -> list[dict]:
    if config.storage == "file":
        return dataframe_records(fetch_file_candle_summary(config.data_dir, file_format=config.file_format))
    engine = get_engine()
    return dataframe_records(fetch_candle_summary(engine))


@app.get("/candles")
def candles(
    config: Annotated[ImportConfig, Depends(get_config)],
    symbol: str = Query(..., description="Broker symbol, for example EURUSD or XAUUSD.pc."),
    timeframe: str = Query(..., description="Timeframe such as M5, M15, H1, H4, or D1."),
    start: datetime | None = Query(None, description="Optional inclusive start time."),
    end: datetime | None = Query(None, description="Optional inclusive end time."),
    limit: int = Query(MAX_CHART_CANDLES, ge=1, le=MAX_CHART_CANDLES, description="Maximum candles to return."),
) -> dict:
    effective_start = start or chart_window_start(end or datetime.now(UTC))
    if config.storage == "file":
        rows = fetch_file_candles(
            config.data_dir,
            symbol=symbol,
            timeframe=timeframe,
            file_format=config.file_format,
            start=effective_start,
            end=end,
            limit=limit,
        )
    else:
        rows = fetch_candles(
            get_engine(),
            symbol=symbol,
            timeframe=timeframe,
            start=effective_start,
            end=end,
            limit=limit,
        )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(rows),
        "candles": dataframe_records(rows),
    }


@app.get("/context/overlays")
def context_overlays(
    config: Annotated[ImportConfig, Depends(get_config)],
    symbol: str = Query(..., description="Broker symbol, for example EURUSD or XAUUSD.pc."),
    timeframe: str = Query(..., description="Chart timeframe such as M5, M15, H1, H4, or D1."),
    start: datetime | None = Query(None, description="Optional inclusive start time."),
    end: datetime | None = Query(None, description="Optional inclusive end time."),
    limit: int = Query(MAX_CHART_CANDLES, ge=100, le=MAX_CHART_CANDLES, description="Maximum chart candles to contextualize."),
) -> dict:
    effective_start = start or chart_window_start(end or datetime.now(UTC))
    if config.storage == "file":
        return build_sb_overlays(
            config.data_dir,
            symbol=symbol,
            timeframe=timeframe,
            start=effective_start,
            end=end,
            limit=limit,
            fetcher=lambda data_dir, **kwargs: fetch_file_candles(
                data_dir,
                file_format=config.file_format,
                **kwargs,
            ),
        )

    return build_sb_overlays(
        get_engine(),
        symbol=symbol,
        timeframe=timeframe,
        start=effective_start,
        end=end,
        limit=limit,
    )


@app.get("/daily-checklist")
def daily_checklist(
    config: Annotated[ImportConfig, Depends(get_config)],
    date_: str | None = Query(None, alias="date", description="Optional target date in YYYY-MM-DD format."),
) -> dict:
    target_date = None
    if date_:
        try:
            target_date = datetime.fromisoformat(date_).date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="date must use YYYY-MM-DD format.") from exc

    if config.storage == "file":
        summary = fetch_file_candle_summary(config.data_dir, file_format=config.file_format)
        symbols = _symbols_with_daily(summary)
        return build_daily_checklist(
            config.data_dir,
            symbols=symbols,
            target_date=target_date,
            fetcher=lambda data_dir, **kwargs: fetch_file_candles(
                data_dir,
                file_format=config.file_format,
                **kwargs,
            ),
        )

    summary = fetch_candle_summary(get_engine())
    return build_daily_checklist(
        get_engine(),
        symbols=_symbols_with_daily(summary),
        target_date=target_date,
    )


@app.put("/daily-checklist/state")
def update_daily_checklist_state(payload: Annotated[dict, Body(...)]) -> dict:
    try:
        return save_checklist_state(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/research/status")
def research_status(
    library: Annotated[ResearchLibrary, Depends(get_research_library)],
    agent: Annotated[SBResearchAgent, Depends(get_research_agent)],
) -> dict:
    return {
        **library.status(),
        "ai": agent.status(),
        "setup_types": sorted(SETUP_TAXONOMY),
    }


@app.post("/research/index")
def research_index(
    payload: Annotated[dict, Body(...)],
    library: Annotated[ResearchLibrary, Depends(get_research_library)],
) -> dict:
    try:
        return library.index_documents(rebuild=bool(payload.get("rebuild", False)))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/research/documents")
def research_documents(
    library: Annotated[ResearchLibrary, Depends(get_research_library)],
    category: str | None = Query(None),
    setup: str | None = Query(None),
) -> list[dict]:
    return library.documents(category=category, setup=setup)


@app.get("/research/search")
def research_search(
    library: Annotated[ResearchLibrary, Depends(get_research_library)],
    query: str = Query(..., min_length=2, max_length=500),
    setup: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(12, ge=1, le=50),
) -> dict:
    try:
        return library.search(
            query,
            setup=setup,
            category=category,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/research/documents/{document_id}/file")
def research_document_file(
    document_id: str,
    library: Annotated[ResearchLibrary, Depends(get_research_library)],
) -> FileResponse:
    try:
        path = library.document_path(document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Research document not found.") from exc
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@app.get("/research/documents/{document_id}/pages/{page}.png")
def research_document_page(
    document_id: str,
    page: int,
    library: Annotated[ResearchLibrary, Depends(get_research_library)],
) -> FileResponse:
    try:
        path = library.render_page(document_id, page)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Research document not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FileResponse(path, media_type="image/png")


@app.post("/research/analyze")
def research_analyze(
    payload: Annotated[dict, Body(...)],
    config: Annotated[ImportConfig, Depends(get_config)],
    agent: Annotated[SBResearchAgent, Depends(get_research_agent)],
) -> dict:
    question = str(payload.get("question", "")).strip()
    symbol = _optional_string(payload.get("symbol"))
    timeframe = _optional_string(payload.get("timeframe"))
    setup = _optional_string(payload.get("setup"))
    try:
        return agent.analyze(
            question=question,
            symbol=symbol,
            timeframe=timeframe,
            setup=setup,
            market_context=_research_market_context(config, symbol),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/research/vision")
def research_vision(
    payload: Annotated[dict, Body(...)],
    agent: Annotated[SBResearchAgent, Depends(get_research_agent)],
) -> dict:
    document_id = str(payload.get("document_id", "")).strip()
    page = payload.get("page")
    if not document_id or not isinstance(page, int):
        raise HTTPException(
            status_code=400, detail="document_id and integer page are required."
        )
    try:
        return agent.analyze_document_page(
            document_id=document_id,
            page=page,
            question=str(payload.get("question", "")).strip(),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Research document not found.") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/runtime/settings")
def runtime_settings() -> dict:
    return _runtime_settings_payload()


@app.put("/runtime/settings")
def update_runtime_settings(payload: Annotated[dict, Body(...)]) -> dict:
    settings = save_runtime_settings(runtime_settings_from_payload(payload))
    return _runtime_settings_payload(settings)


@app.get("/notifications/telegram/status")
def telegram_status(
    notifier: Annotated[TelegramNotifier, Depends(get_telegram_notifier)],
) -> dict:
    return notifier.status()


@app.post("/notifications/telegram/test")
def telegram_test(
    notifier: Annotated[TelegramNotifier, Depends(get_telegram_notifier)],
) -> dict:
    try:
        return notifier.send_test()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _runtime_settings_payload(settings: RuntimeSettings | None = None) -> dict:
    current = settings or load_runtime_settings()
    return {"update_interval_minutes": current.update_interval_minutes}


def _symbols_with_daily(summary) -> list[str]:
    if summary.empty:
        return []

    daily = summary[summary["timeframe"] == "D1"]
    source = daily if not daily.empty else summary
    return sorted(set(source["broker_symbol"].dropna().astype(str)))


def _optional_string(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _research_market_context(
    config: ImportConfig, symbol: str | None
) -> dict | None:
    if not symbol:
        return None
    if config.storage == "file":
        checklist = build_daily_checklist(
            config.data_dir,
            symbols=[symbol],
            fetcher=lambda data_dir, **kwargs: fetch_file_candles(
                data_dir,
                file_format=config.file_format,
                **kwargs,
            ),
        )
    else:
        checklist = build_daily_checklist(get_engine(), symbols=[symbol])
    if not checklist["rows"]:
        return None
    row = checklist["rows"][0]
    return {
        "symbol": row["symbol"],
        "last_candle_time": row["last_candle_time"],
        "signal_days": row["signal_days"],
        "previous_signal_days": row["previous_signal_days"],
        "weekly_template_state": row["weekly_template_state"],
        "price_location": row["price_location"],
        "candidate_direction": row["candidate_direction"],
        "quality_score": row["quality_score"],
        "no_trade_reasons": row["no_trade_reasons"],
        "context": row["context"],
    }

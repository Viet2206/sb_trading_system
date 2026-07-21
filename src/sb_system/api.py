from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from sb_system.context import build_sb_overlays
from sb_system.file_store import (
    fetch_file_candle_summary,
    fetch_file_candles,
    fetch_file_symbols,
)
from sb_system.market_data import (
    ImportConfig,
    check_connection,
    create_db_engine,
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


app = FastAPI(
    title="SB Trading System API",
    version="0.1.0",
    description="Research API for imported MT5 candle data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "PUT"],
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
    return create_db_engine(config.database_url)


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
    symbol: str = Query(..., description="Broker symbol, for example EURUSD or XAUUSD+."),
    timeframe: str = Query(..., description="Timeframe such as M5, M15, H1, H4, or D1."),
    start: datetime | None = Query(None, description="Optional inclusive start time."),
    end: datetime | None = Query(None, description="Optional inclusive end time."),
    limit: int | None = Query(None, ge=1, le=200_000, description="Optional maximum candles to return."),
) -> dict:
    if config.storage == "file":
        rows = fetch_file_candles(
            config.data_dir,
            symbol=symbol,
            timeframe=timeframe,
            file_format=config.file_format,
            start=start,
            end=end,
            limit=limit,
        )
    else:
        rows = fetch_candles(
            get_engine(),
            symbol=symbol,
            timeframe=timeframe,
            start=start,
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
    symbol: str = Query(..., description="Broker symbol, for example EURUSD or XAUUSD+."),
    timeframe: str = Query(..., description="Chart timeframe such as M5, M15, H1, H4, or D1."),
    start: datetime | None = Query(None, description="Optional inclusive start time."),
    end: datetime | None = Query(None, description="Optional inclusive end time."),
    limit: int | None = Query(None, ge=100, le=200_000, description="Optional maximum chart candles to contextualize."),
) -> dict:
    if config.storage == "file":
        return build_sb_overlays(
            config.data_dir,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
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
        start=start,
        end=end,
        limit=limit,
    )


@app.get("/runtime/settings")
def runtime_settings() -> dict:
    return _runtime_settings_payload()


@app.put("/runtime/settings")
def update_runtime_settings(payload: Annotated[dict, Body(...)]) -> dict:
    settings = save_runtime_settings(runtime_settings_from_payload(payload))
    return _runtime_settings_payload(settings)


def _runtime_settings_payload(settings: RuntimeSettings | None = None) -> dict:
    current = settings or load_runtime_settings()
    return {"update_interval_minutes": current.update_interval_minutes}

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from sb_system.context import build_sb_overlays
from sb_system.market_data import (
    check_connection,
    create_db_engine,
    dataframe_records,
    fetch_candle_summary,
    fetch_candles,
    fetch_symbols,
    load_config,
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
    allow_methods=["GET"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    config = load_config()
    if not config.database_url:
        raise RuntimeError("DATABASE_URL is required.")
    return create_db_engine(config.database_url)


@app.get("/health")
def health(engine: Annotated[Engine, Depends(get_engine)]) -> dict:
    try:
        rows = dataframe_records(check_connection(engine))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return {"status": "ok", "database": rows[0] if rows else None}


@app.get("/symbols")
def symbols(engine: Annotated[Engine, Depends(get_engine)]) -> list[dict]:
    return dataframe_records(fetch_symbols(engine))


@app.get("/candles/summary")
def candle_summary(engine: Annotated[Engine, Depends(get_engine)]) -> list[dict]:
    return dataframe_records(fetch_candle_summary(engine))


@app.get("/candles")
def candles(
    engine: Annotated[Engine, Depends(get_engine)],
    symbol: str = Query(..., description="Broker symbol, for example EURUSD or XAUUSD+."),
    timeframe: str = Query(..., description="Timeframe such as M5, M15, H1, H4, or D1."),
    start: datetime | None = Query(None, description="Optional inclusive start time."),
    end: datetime | None = Query(None, description="Optional inclusive end time."),
    limit: int | None = Query(None, ge=1, le=200_000, description="Optional maximum candles to return."),
) -> dict:
    rows = fetch_candles(
        engine,
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
    engine: Annotated[Engine, Depends(get_engine)],
    symbol: str = Query(..., description="Broker symbol, for example EURUSD or XAUUSD+."),
    timeframe: str = Query(..., description="Chart timeframe such as M5, M15, H1, H4, or D1."),
    start: datetime | None = Query(None, description="Optional inclusive start time."),
    end: datetime | None = Query(None, description="Optional inclusive end time."),
    limit: int | None = Query(None, ge=100, le=200_000, description="Optional maximum chart candles to contextualize."),
) -> dict:
    return build_sb_overlays(
        engine,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
    )

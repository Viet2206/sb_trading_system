from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
from dotenv import load_dotenv

from sb_system.market_data import PROJECT_ROOT, _split_env


CTRADER_TIMEFRAME_PERIODS = {
    "M1": "M1",
    "M2": "M2",
    "M3": "M3",
    "M4": "M4",
    "M5": "M5",
    "M10": "M10",
    "M15": "M15",
    "M30": "M30",
    "H1": "H1",
    "H4": "H4",
    "H12": "H12",
    "D1": "D1",
    "W1": "W1",
    "MN1": "MN1",
}

TIMEFRAME_SECONDS = {
    "M1": 60,
    "M2": 2 * 60,
    "M3": 3 * 60,
    "M4": 4 * 60,
    "M5": 5 * 60,
    "M10": 10 * 60,
    "M15": 15 * 60,
    "M30": 30 * 60,
    "H1": 60 * 60,
    "H4": 4 * 60 * 60,
    "H12": 12 * 60 * 60,
    "D1": 24 * 60 * 60,
    "W1": 7 * 24 * 60 * 60,
}

DEFAULT_CHUNK_DAYS = {
    "M1": 7,
    "M2": 10,
    "M3": 14,
    "M4": 20,
    "M5": 30,
    "M10": 45,
    "M15": 60,
    "M30": 90,
    "H1": 180,
    "H4": 365,
    "H12": 730,
    "D1": 1200,
    "W1": 2400,
}


@dataclass(frozen=True)
class CTraderConfig:
    client_id: str | None
    client_secret: str | None
    access_token: str | None
    account_id: int | None
    host_type: str
    symbols: list[str]
    timeframes: list[str]
    import_start: date
    chunk_days: dict[str, int]


def load_ctrader_config(env_path: str | Path | None = None) -> CTraderConfig:
    if env_path:
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(PROJECT_ROOT / ".env", override=True)

    account_id = os.getenv("CTRADER_ACCOUNT_ID")
    host_type = os.getenv("CTRADER_HOST_TYPE", "demo").strip().lower()
    if host_type not in {"demo", "live"}:
        raise ValueError("CTRADER_HOST_TYPE must be either 'demo' or 'live'.")

    symbols_default = os.getenv("SB_SYMBOLS", "EURUSD,GBPUSD,USDJPY,AUDUSD,XAUUSD,NAS100,SP500")
    symbols = _split_env("CTRADER_SYMBOLS", symbols_default)
    timeframes = _split_env("CTRADER_TIMEFRAMES", os.getenv("SB_TIMEFRAMES", "M5,M15,H1,H4,D1"))

    return CTraderConfig(
        client_id=os.getenv("CTRADER_CLIENT_ID"),
        client_secret=os.getenv("CTRADER_CLIENT_SECRET"),
        access_token=os.getenv("CTRADER_ACCESS_TOKEN"),
        account_id=int(account_id) if account_id else None,
        host_type=host_type,
        symbols=symbols,
        timeframes=timeframes,
        import_start=date.fromisoformat(os.getenv("CTRADER_IMPORT_START", os.getenv("SB_IMPORT_START", "2026-01-01"))),
        chunk_days=_load_chunk_days(),
    )


def validate_ctrader_config(config: CTraderConfig) -> None:
    missing = []
    if not config.client_id:
        missing.append("CTRADER_CLIENT_ID")
    if not config.client_secret:
        missing.append("CTRADER_CLIENT_SECRET")
    if not config.access_token:
        missing.append("CTRADER_ACCESS_TOKEN")
    if config.account_id is None:
        missing.append("CTRADER_ACCOUNT_ID")
    if missing:
        raise ValueError(
            "Missing cTrader Open API settings: "
            + ", ".join(missing)
            + ". Create a cTrader Open API application and update .env."
        )


def normalize_trendbars(
    trendbars: Iterable,
    *,
    symbol: str,
    timeframe: str,
    digits: int,
) -> pd.DataFrame:
    rows = []
    for trendbar in trendbars:
        low_relative = int(trendbar.low)
        rows.append(
            {
                "broker_symbol": symbol,
                "timeframe": timeframe,
                "candle_time": datetime.fromtimestamp(int(trendbar.utcTimestampInMinutes) * 60, tz=UTC),
                "open": _relative_price(low_relative + int(trendbar.deltaOpen), digits),
                "high": _relative_price(low_relative + int(trendbar.deltaHigh), digits),
                "low": _relative_price(low_relative, digits),
                "close": _relative_price(low_relative + int(trendbar.deltaClose), digits),
                "tick_volume": int(trendbar.volume),
                "spread": 0,
                "real_volume": 0,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "broker_symbol",
                "timeframe",
                "candle_time",
                "open",
                "high",
                "low",
                "close",
                "tick_volume",
                "spread",
                "real_volume",
            ]
        )

    return pd.DataFrame(rows).sort_values("candle_time").reset_index(drop=True)


def timeframe_overlap(timeframe: str, lookback_candles: int) -> timedelta:
    seconds = TIMEFRAME_SECONDS.get(timeframe, 60 * 60)
    return timedelta(seconds=seconds * max(1, lookback_candles))


def chunk_ranges(start: datetime, end: datetime, *, timeframe: str, chunk_days: dict[str, int]) -> list[tuple[datetime, datetime]]:
    max_days = chunk_days.get(timeframe, DEFAULT_CHUNK_DAYS.get(timeframe, 30))
    step = timedelta(days=max(1, max_days))
    ranges: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor < end:
        next_end = min(cursor + step, end)
        ranges.append((cursor, next_end))
        cursor = next_end
    return ranges


def utc_datetime_from_date(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _relative_price(relative: int, digits: int) -> float:
    return round(relative / 100000.0, digits)


def _load_chunk_days() -> dict[str, int]:
    raw = os.getenv("CTRADER_CHUNK_DAYS", "").strip()
    chunks = dict(DEFAULT_CHUNK_DAYS)
    if not raw:
        return chunks

    for item in raw.split(","):
        if not item.strip() or ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip().upper()
        if key in CTRADER_TIMEFRAME_PERIODS:
            chunks[key] = max(1, int(value.strip()))
    return chunks

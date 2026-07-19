from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "sql" / "001_market_data.sql"


@dataclass(frozen=True)
class ImportConfig:
    database_url: str | None
    symbols: list[str]
    timeframes: list[str]
    import_start: date


def load_config(env_path: str | Path | None = None, *, require_database_url: bool = True) -> ImportConfig:
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv(PROJECT_ROOT / ".env")

    database_url = os.getenv("DATABASE_URL")
    if require_database_url and not database_url:
        raise ValueError("DATABASE_URL is required. Copy .env.example to .env and update it.")

    symbols = _split_env("SB_SYMBOLS", "EURUSD,GBPUSD,USDJPY,XAUUSD+,NAS100.r,SP500.r")
    timeframes = _split_env("SB_TIMEFRAMES", "M1,M5,M15,H1,H4,D1")
    import_start = date.fromisoformat(os.getenv("SB_IMPORT_START", "2026-01-01"))

    return ImportConfig(
        database_url=database_url,
        symbols=symbols,
        timeframes=timeframes,
        import_start=import_start,
    )


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def create_schema(engine: Engine) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))


def check_connection(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(
            text(
                """
                SELECT
                    current_database() AS database,
                    current_user AS username,
                    now() AS server_time
                """
            ),
            conn,
        )


def normalize_rates(rates: Iterable[dict] | pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
    df = pd.DataFrame(rates)
    if df.empty:
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

    if "time" not in df.columns:
        raise ValueError("MT5 rates must include a 'time' column.")

    df = df.copy()
    df["broker_symbol"] = symbol
    df["timeframe"] = timeframe
    df["candle_time"] = pd.to_datetime(df["time"], unit="s", utc=True)

    columns = [
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
    return df[columns].sort_values("candle_time").reset_index(drop=True)


def upsert_symbol(
    engine: Engine,
    broker_symbol: str,
    *,
    base_symbol: str | None = None,
    description: str | None = None,
    digits: int | None = None,
    point: float | None = None,
    trade_contract_size: float | None = None,
    currency_base: str | None = None,
    currency_profit: str | None = None,
    currency_margin: str | None = None,
) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO market.symbols (
                    broker_symbol,
                    base_symbol,
                    description,
                    digits,
                    point,
                    trade_contract_size,
                    currency_base,
                    currency_profit,
                    currency_margin
                )
                VALUES (
                    :broker_symbol,
                    :base_symbol,
                    :description,
                    :digits,
                    :point,
                    :trade_contract_size,
                    :currency_base,
                    :currency_profit,
                    :currency_margin
                )
                ON CONFLICT (broker_symbol) DO UPDATE SET
                    base_symbol = COALESCE(EXCLUDED.base_symbol, market.symbols.base_symbol),
                    description = COALESCE(EXCLUDED.description, market.symbols.description),
                    digits = COALESCE(EXCLUDED.digits, market.symbols.digits),
                    point = COALESCE(EXCLUDED.point, market.symbols.point),
                    trade_contract_size = COALESCE(EXCLUDED.trade_contract_size, market.symbols.trade_contract_size),
                    currency_base = COALESCE(EXCLUDED.currency_base, market.symbols.currency_base),
                    currency_profit = COALESCE(EXCLUDED.currency_profit, market.symbols.currency_profit),
                    currency_margin = COALESCE(EXCLUDED.currency_margin, market.symbols.currency_margin),
                    updated_at = now()
                RETURNING symbol_id
                """
            ),
            {
                "broker_symbol": broker_symbol,
                "base_symbol": base_symbol,
                "description": description,
                "digits": digits,
                "point": point,
                "trade_contract_size": trade_contract_size,
                "currency_base": currency_base,
                "currency_profit": currency_profit,
                "currency_margin": currency_margin,
            },
        ).one()
    return int(row.symbol_id)


def upsert_candles(engine: Engine, candles: pd.DataFrame) -> int:
    if candles.empty:
        return 0

    required_columns = {
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
    }
    missing = required_columns.difference(candles.columns)
    if missing:
        raise ValueError(f"Missing required candle columns: {sorted(missing)}")

    rows = candles.copy()
    rows["candle_time"] = pd.to_datetime(rows["candle_time"], utc=True)
    payload = rows.to_dict(orient="records")

    with engine.begin() as conn:
        for broker_symbol in sorted(rows["broker_symbol"].unique()):
            conn.execute(
                text(
                    """
                    INSERT INTO market.symbols (broker_symbol)
                    VALUES (:broker_symbol)
                    ON CONFLICT (broker_symbol) DO NOTHING
                    """
                ),
                {"broker_symbol": broker_symbol},
            )

        conn.execute(
            text(
                """
                INSERT INTO market.candles (
                    symbol_id,
                    timeframe,
                    candle_time,
                    open,
                    high,
                    low,
                    close,
                    tick_volume,
                    spread,
                    real_volume
                )
                SELECT
                    s.symbol_id,
                    :timeframe,
                    :candle_time,
                    :open,
                    :high,
                    :low,
                    :close,
                    :tick_volume,
                    :spread,
                    :real_volume
                FROM market.symbols s
                WHERE s.broker_symbol = :broker_symbol
                ON CONFLICT (symbol_id, timeframe, candle_time) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    tick_volume = EXCLUDED.tick_volume,
                    spread = EXCLUDED.spread,
                    real_volume = EXCLUDED.real_volume,
                    updated_at = now()
                """
            ),
            payload,
        )

    return len(payload)


def fetch_candle_summary(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(
            text(
                """
                SELECT
                    s.broker_symbol,
                    c.timeframe,
                    min(c.candle_time) AS first_candle,
                    max(c.candle_time) AS last_candle,
                    count(*) AS candles
                FROM market.candles c
                JOIN market.symbols s ON s.symbol_id = c.symbol_id
                GROUP BY s.broker_symbol, c.timeframe
                ORDER BY s.broker_symbol, c.timeframe
                """
            ),
            conn,
        )


def fetch_symbols(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(
            text(
                """
                SELECT
                    s.broker_symbol,
                    s.base_symbol,
                    s.description,
                    s.digits,
                    s.point,
                    s.trade_contract_size,
                    s.currency_base,
                    s.currency_profit,
                    s.currency_margin,
                    min(c.candle_time) AS first_candle,
                    max(c.candle_time) AS last_candle,
                    count(c.candle_id) AS candles
                FROM market.symbols s
                LEFT JOIN market.candles c ON c.symbol_id = s.symbol_id
                GROUP BY
                    s.symbol_id,
                    s.broker_symbol,
                    s.base_symbol,
                    s.description,
                    s.digits,
                    s.point,
                    s.trade_contract_size,
                    s.currency_base,
                    s.currency_profit,
                    s.currency_margin
                ORDER BY s.broker_symbol
                """
            ),
            conn,
        )


def fetch_candles(
    engine: Engine,
    *,
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    conditions = ["s.broker_symbol = :symbol", "c.timeframe = :timeframe"]
    params: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "limit": limit,
    }

    if start is not None:
        conditions.append("c.candle_time >= :start_time")
        params["start_time"] = start

    if end is not None:
        conditions.append("c.candle_time <= :end_time")
        params["end_time"] = end

    where_clause = "\n                      AND ".join(conditions)

    with engine.connect() as conn:
        return pd.read_sql_query(
            text(
                f"""
                WITH selected_candles AS (
                    SELECT
                        s.broker_symbol,
                        c.timeframe,
                        c.candle_time,
                        c.open,
                        c.high,
                        c.low,
                        c.close,
                        c.tick_volume,
                        c.spread,
                        c.real_volume
                    FROM market.candles c
                    JOIN market.symbols s ON s.symbol_id = c.symbol_id
                    WHERE {where_clause}
                    ORDER BY c.candle_time DESC
                    LIMIT :limit
                )
                SELECT *
                FROM selected_candles
                ORDER BY candle_time ASC
                """
            ),
            conn,
            params=params,
        )


def dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [_json_safe_record(record) for record in df.to_dict(orient="records")]


def start_import_run(
    engine: Engine,
    *,
    source: str,
    symbols: list[str],
    timeframes: list[str],
    started_from: datetime,
    notes: str | None = None,
) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO market.import_runs (source, symbols, timeframes, started_from, notes)
                VALUES (:source, :symbols, :timeframes, :started_from, :notes)
                RETURNING import_run_id
                """
            ),
            {
                "source": source,
                "symbols": symbols,
                "timeframes": timeframes,
                "started_from": started_from,
                "notes": notes,
            },
        ).one()
    return int(row.import_run_id)


def finish_import_run(engine: Engine, import_run_id: int, *, status: str, rows_imported: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE market.import_runs
                SET finished_at = now(), status = :status, rows_imported = :rows_imported
                WHERE import_run_id = :import_run_id
                """
            ),
            {
                "import_run_id": import_run_id,
                "status": status,
                "rows_imported": rows_imported,
            },
        )


def utc_datetime_from_date(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _split_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _json_safe_record(record: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in record.items():
        if pd.isna(value):
            safe[key] = None
        elif isinstance(value, pd.Timestamp):
            safe[key] = value.isoformat()
        elif isinstance(value, datetime):
            safe[key] = value.isoformat()
        elif isinstance(value, Decimal):
            safe[key] = float(value)
        else:
            safe[key] = value
    return safe

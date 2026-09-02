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

from sb_system.chart_window import CHART_WINDOW_MONTHS, chart_window_start


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "sql"


@dataclass(frozen=True)
class ImportConfig:
    database_url: str | None
    storage: str
    data_dir: Path
    file_format: str
    symbols: list[str]
    timeframes: list[str]
    import_start: date


def load_config(env_path: str | Path | None = None, *, require_database_url: bool = True) -> ImportConfig:
    if env_path:
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(PROJECT_ROOT / ".env", override=True)

    database_url = os.getenv("DATABASE_URL")
    if require_database_url and not database_url:
        raise ValueError("DATABASE_URL is required. Copy .env.example to .env and update it.")

    storage = os.getenv("SB_STORAGE", "file").strip().lower()
    if storage not in {"postgres", "file"}:
        raise ValueError("SB_STORAGE must be either 'postgres' or 'file'.")

    data_dir = Path(os.getenv("SB_DATA_DIR", str(PROJECT_ROOT / "data" / "market"))).expanduser()
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    file_format = os.getenv("SB_FILE_FORMAT", "csv.gz").strip().lower()
    if file_format not in {"csv", "csv.gz", "parquet"}:
        raise ValueError("SB_FILE_FORMAT must be one of: csv, csv.gz, parquet.")

    symbols = _split_env(
        "SB_SYMBOLS",
        "EURUSD,GBPUSD,USDJPY,AUDUSD,NZDUSD,USDCAD,XAUUSD.pc,NAS100,"
        "BTCUSD.sc,USDCHF.pc,GBPJPY.pc,EURJPY.pc,SP500,AUDCAD.pc,AUDCHF.pc,"
        "AUDJPY.pc,CADCHF.pc,CADJPY.pc,CHFJPY.pc,COPPER-C,EURAUD.pc,EURCAD.pc,"
        "EURCHF.pc,EURGBP.pc,GBPAUD.pc,GBPCAD.pc,GBPCHF.pc,USOUSD.pc",
    )
    timeframes = _split_env("SB_TIMEFRAMES", "M5,M15,H1,H4,D1")
    history_months_value = os.getenv("SB_HISTORY_MONTHS", str(CHART_WINDOW_MONTHS)).strip()
    if history_months_value:
        history_months = int(history_months_value)
        if history_months < 1 or history_months > 120:
            raise ValueError("SB_HISTORY_MONTHS must be between 1 and 120.")
        import_start = chart_window_start(months=history_months).date()
    else:
        import_start = date.fromisoformat(os.getenv("SB_IMPORT_START", "2026-01-01"))

    return ImportConfig(
        database_url=database_url,
        storage=storage,
        data_dir=data_dir,
        file_format=file_format,
        symbols=symbols,
        timeframes=timeframes,
        import_start=import_start,
    )


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def create_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS market"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS market.schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        applied = set(
            conn.execute(text("SELECT version FROM market.schema_migrations")).scalars()
        )
        for schema_path in sorted(SCHEMA_DIR.glob("[0-9][0-9][0-9]_*.sql")):
            version = schema_path.stem
            if version in applied:
                continue
            sql = schema_path.read_text(encoding="utf-8")
            statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
            for statement in statements:
                conn.execute(text(statement))
            conn.execute(
                text("INSERT INTO market.schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )


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


def upsert_candles(
    engine: Engine,
    candles: pd.DataFrame,
    *,
    source: str = "mt5",
    retain_from: datetime | None = None,
) -> int:
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
    rows = rows.drop_duplicates(
        subset=["broker_symbol", "timeframe", "candle_time"],
        keep="last",
    )
    payload = [
        {
            **{column: _database_value(value) for column, value in row.items()},
            "source": source,
        }
        for row in rows.to_dict(orient="records")
    ]
    pairs = sorted(
        {
            (str(row["broker_symbol"]), str(row["timeframe"]))
            for row in payload
        }
    )

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

        _copy_candle_payload(conn, payload)

        for broker_symbol, timeframe in pairs:
            pair_params: dict[str, Any] = {
                "broker_symbol": broker_symbol,
                "timeframe": timeframe,
            }
            if retain_from is not None:
                pair_params["retain_from"] = retain_from
                conn.execute(
                    text(
                        """
                        DELETE FROM market.candles c
                        USING market.symbols s
                        WHERE c.symbol_id = s.symbol_id
                          AND s.broker_symbol = :broker_symbol
                          AND c.timeframe = :timeframe
                          AND c.candle_time < :retain_from
                        """
                    ),
                    pair_params,
                )
            _refresh_candle_summary(conn, broker_symbol, timeframe)

    return len(payload)


def fetch_candle_summary(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql_query(
            text(
                """
                SELECT
                    s.broker_symbol,
                    cs.timeframe,
                    cs.first_candle,
                    cs.last_candle,
                    cs.candles
                FROM market.candle_summary cs
                JOIN market.symbols s ON s.symbol_id = cs.symbol_id
                ORDER BY s.broker_symbol, cs.timeframe
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
                    min(cs.first_candle) AS first_candle,
                    max(cs.last_candle) AS last_candle,
                    COALESCE(sum(cs.candles), 0) AS candles
                FROM market.symbols s
                LEFT JOIN market.candle_summary cs ON cs.symbol_id = s.symbol_id
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
    limit: int | None = 500,
) -> pd.DataFrame:
    conditions = ["s.broker_symbol = :symbol", "c.timeframe = :timeframe"]
    params: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
    }
    limit_clause = ""
    if limit is not None:
        params["limit"] = limit
        limit_clause = "LIMIT :limit"

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
                    {limit_clause}
                )
                SELECT *
                FROM selected_candles
                ORDER BY candle_time ASC
                """
            ),
            conn,
            params=params,
        )


def latest_candle_time(
    engine: Engine,
    *,
    symbol: str,
    timeframe: str,
) -> pd.Timestamp | None:
    with engine.connect() as conn:
        value = conn.execute(
            text(
                """
                SELECT cs.last_candle
                FROM market.candle_summary cs
                JOIN market.symbols s ON s.symbol_id = cs.symbol_id
                WHERE s.broker_symbol = :symbol
                  AND cs.timeframe = :timeframe
                """
            ),
            {"symbol": symbol, "timeframe": timeframe},
        ).scalar_one_or_none()
    return pd.Timestamp(value) if value is not None else None


def prune_candles_before(engine: Engine, retain_from: datetime) -> int:
    with engine.begin() as conn:
        deleted = conn.execute(
            text("DELETE FROM market.candles WHERE candle_time < :retain_from"),
            {"retain_from": retain_from},
        ).rowcount
        conn.execute(text("TRUNCATE market.candle_summary"))
        conn.execute(
            text(
                """
                INSERT INTO market.candle_summary (
                    symbol_id, timeframe, first_candle, last_candle, candles, updated_at
                )
                SELECT symbol_id, timeframe, min(candle_time), max(candle_time), count(*), now()
                FROM market.candles
                GROUP BY symbol_id, timeframe
                """
            )
        )
    return int(deleted or 0)


def _refresh_candle_summary(conn, broker_symbol: str, timeframe: str) -> None:
    result = conn.execute(
        text(
            """
            INSERT INTO market.candle_summary (
                symbol_id, timeframe, first_candle, last_candle, candles, updated_at
            )
            SELECT
                s.symbol_id,
                :timeframe,
                min(c.candle_time),
                max(c.candle_time),
                count(*),
                now()
            FROM market.symbols s
            JOIN market.candles c ON c.symbol_id = s.symbol_id
            WHERE s.broker_symbol = :broker_symbol
              AND c.timeframe = :timeframe
            GROUP BY s.symbol_id
            ON CONFLICT (symbol_id, timeframe) DO UPDATE SET
                first_candle = EXCLUDED.first_candle,
                last_candle = EXCLUDED.last_candle,
                candles = EXCLUDED.candles,
                updated_at = now()
            """
        ),
        {"broker_symbol": broker_symbol, "timeframe": timeframe},
    )
    if result.rowcount == 0:
        conn.execute(
            text(
                """
                DELETE FROM market.candle_summary cs
                USING market.symbols s
                WHERE cs.symbol_id = s.symbol_id
                  AND s.broker_symbol = :broker_symbol
                  AND cs.timeframe = :timeframe
                """
            ),
            {"broker_symbol": broker_symbol, "timeframe": timeframe},
        )


def _database_value(value):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value.item() if hasattr(value, "item") else value


def _copy_candle_payload(conn, payload: list[dict[str, Any]]) -> None:
    """Bulk stage candle rows with PostgreSQL COPY, then merge them atomically."""
    conn.execute(
        text(
            """
            CREATE TEMP TABLE sb_candle_stage (
                broker_symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                candle_time TIMESTAMPTZ NOT NULL,
                open NUMERIC(20, 10) NOT NULL,
                high NUMERIC(20, 10) NOT NULL,
                low NUMERIC(20, 10) NOT NULL,
                close NUMERIC(20, 10) NOT NULL,
                tick_volume BIGINT,
                spread INTEGER,
                real_volume BIGINT,
                source TEXT NOT NULL
            ) ON COMMIT DROP
            """
        )
    )
    columns = (
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
        "source",
    )
    raw_connection = conn.connection.driver_connection
    with raw_connection.cursor() as cursor:
        with cursor.copy(
            "COPY sb_candle_stage (broker_symbol, timeframe, candle_time, open, high, low, close, "
            "tick_volume, spread, real_volume, source) FROM STDIN"
        ) as copy:
            for row in payload:
                copy.write_row(tuple(row[column] for column in columns))

    conn.execute(
        text(
            """
            INSERT INTO market.candles (
                symbol_id, timeframe, candle_time, open, high, low, close,
                tick_volume, spread, real_volume, source
            )
            SELECT
                s.symbol_id,
                stage.timeframe,
                stage.candle_time,
                stage.open,
                stage.high,
                stage.low,
                stage.close,
                stage.tick_volume,
                stage.spread,
                stage.real_volume,
                stage.source
            FROM sb_candle_stage stage
            JOIN market.symbols s ON s.broker_symbol = stage.broker_symbol
            ON CONFLICT (symbol_id, timeframe, candle_time) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                tick_volume = EXCLUDED.tick_volume,
                spread = EXCLUDED.spread,
                real_volume = EXCLUDED.real_volume,
                source = EXCLUDED.source,
                updated_at = now()
            """
        )
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

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.file_store import latest_file_candle_time, upsert_file_candles
from sb_system.market_data import (
    check_connection,
    create_db_engine,
    create_schema,
    latest_candle_time,
    load_config,
    normalize_rates,
    prune_candles_before,
    upsert_candles,
    utc_datetime_from_date,
)
from sb_system.runtime_settings import (
    RuntimeSettings,
    load_runtime_settings,
    save_runtime_settings,
)


TIMEFRAME_SECONDS = {
    "M1": 60,
    "M2": 2 * 60,
    "M3": 3 * 60,
    "M4": 4 * 60,
    "M5": 5 * 60,
    "M6": 6 * 60,
    "M10": 10 * 60,
    "M12": 12 * 60,
    "M15": 15 * 60,
    "M20": 20 * 60,
    "M30": 30 * 60,
    "H1": 60 * 60,
    "H2": 2 * 60 * 60,
    "H3": 3 * 60 * 60,
    "H4": 4 * 60 * 60,
    "H6": 6 * 60 * 60,
    "H8": 8 * 60 * 60,
    "H12": 12 * 60 * 60,
    "D1": 24 * 60 * 60,
    "W1": 7 * 24 * 60 * 60,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Poll MetaTrader 5 candles into SB Trading System storage."
    )
    parser.add_argument(
        "--env",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env file with SB symbols, timeframes, and storage settings.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one MT5 update cycle, then exit.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        help="Set the shared update interval used by this script and the UI.",
    )
    parser.add_argument(
        "--lookback-candles",
        type=int,
        default=10,
        help="Re-request this many candles before the latest saved candle to update the active candle safely.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval_minutes is not None:
        save_runtime_settings(RuntimeSettings(update_interval_minutes=args.interval_minutes))

    config = load_config(args.env, require_database_url=False)
    engine = None
    if config.storage == "postgres":
        if not config.database_url:
            print("DATABASE_URL is required when SB_STORAGE=postgres.")
            return 1
        engine = create_db_engine(config.database_url)
        create_schema(engine)
        connection = check_connection(engine).iloc[0]
        print(f"PostgreSQL: {connection['database']} as {connection['username']}")
        removed = prune_candles_before(engine, utc_datetime_from_date(config.import_start))
        if removed:
            print(f"PostgreSQL retention removed {removed} expired candles")

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 package is not installed in this Python environment.")
        print(f'Run: "{sys.executable}" -m pip install -r requirements-win-mt5.txt')
        return 1

    timeframe_map = _mt5_timeframe_map(mt5)

    if not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        print("Open MetaTrader 5 and log in to your broker account, then retry.")
        return 2

    print(f"Storage: {config.storage}")
    print(f"Data dir: {config.data_dir}")
    print(f"File format: {config.file_format}")
    print(f"Symbols: {', '.join(config.symbols)}")
    print(f"Timeframes: {', '.join(config.timeframes)}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            rows = poll_once(
                mt5,
                timeframe_map,
                data_dir=config.data_dir,
                file_format=config.file_format,
                symbols=config.symbols,
                timeframes=config.timeframes,
                import_start=utc_datetime_from_date(config.import_start),
                lookback_candles=args.lookback_candles,
                engine=engine,
            )
            print(f"{datetime.now(timezone.utc).isoformat()} updated {rows} candles")

            if args.once:
                return 0

            interval_minutes = load_runtime_settings().update_interval_minutes
            print(f"Next update in {interval_minutes} minute(s)")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("Stopped.")
        return 0
    finally:
        mt5.shutdown()


def poll_once(
    mt5,
    timeframe_map: dict[str, int],
    *,
    data_dir: Path,
    file_format: str,
    symbols: list[str],
    timeframes: list[str],
    import_start: datetime,
    lookback_candles: int,
    engine=None,
) -> int:
    date_to = datetime.now(timezone.utc)
    total_rows = 0

    for symbol in symbols:
        if not mt5.symbol_select(symbol, True):
            print(f"SKIP {symbol}: symbol_select failed: {mt5.last_error()}")
            continue

        for timeframe in timeframes:
            mt5_timeframe = timeframe_map.get(timeframe)
            if mt5_timeframe is None:
                print(f"SKIP {symbol} {timeframe}: unsupported timeframe")
                continue

            date_from = _next_fetch_start(
                data_dir,
                symbol=symbol,
                timeframe=timeframe,
                file_format=file_format,
                import_start=import_start,
                lookback_candles=lookback_candles,
                engine=engine,
            )
            rates = mt5.copy_rates_range(symbol, mt5_timeframe, date_from, date_to)
            candles = normalize_rates(rates, symbol=symbol, timeframe=timeframe)
            if engine is None:
                rows = upsert_file_candles(
                    data_dir,
                    candles,
                    file_format=file_format,
                    retain_from=import_start,
                )
            else:
                rows = upsert_candles(
                    engine,
                    candles,
                    source="mt5",
                    retain_from=import_start,
                )
            total_rows += rows
            print(f"{symbol:12} {timeframe:4} {rows:8} candles from {date_from.isoformat()}")

    return total_rows


def _next_fetch_start(
    data_dir: Path,
    *,
    symbol: str,
    timeframe: str,
    file_format: str,
    import_start: datetime,
    lookback_candles: int,
    engine=None,
) -> datetime:
    latest = (
        latest_candle_time(engine, symbol=symbol, timeframe=timeframe)
        if engine is not None
        else latest_file_candle_time(
            data_dir,
            symbol=symbol,
            timeframe=timeframe,
            file_format=file_format,
        )
    )
    if latest is None:
        return import_start

    seconds = TIMEFRAME_SECONDS.get(timeframe, 60 * 60)
    overlap = timedelta(seconds=seconds * max(1, lookback_candles))
    return max(import_start, latest.to_pydatetime() - overlap)


def _mt5_timeframe_map(mt5) -> dict[str, int]:
    return {
        "M1": mt5.TIMEFRAME_M1,
        "M2": mt5.TIMEFRAME_M2,
        "M3": mt5.TIMEFRAME_M3,
        "M4": mt5.TIMEFRAME_M4,
        "M5": mt5.TIMEFRAME_M5,
        "M6": mt5.TIMEFRAME_M6,
        "M10": mt5.TIMEFRAME_M10,
        "M12": mt5.TIMEFRAME_M12,
        "M15": mt5.TIMEFRAME_M15,
        "M20": mt5.TIMEFRAME_M20,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H2": mt5.TIMEFRAME_H2,
        "H3": mt5.TIMEFRAME_H3,
        "H4": mt5.TIMEFRAME_H4,
        "H6": mt5.TIMEFRAME_H6,
        "H8": mt5.TIMEFRAME_H8,
        "H12": mt5.TIMEFRAME_H12,
        "D1": mt5.TIMEFRAME_D1,
        "W1": mt5.TIMEFRAME_W1,
        "MN1": mt5.TIMEFRAME_MN1,
    }


if __name__ == "__main__":
    raise SystemExit(main())

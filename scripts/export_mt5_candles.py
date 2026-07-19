from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.market_data import load_config, normalize_rates, utc_datetime_from_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export MT5 candles to compressed CSV files for offline import on Mac."
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data" / "raw" / "mt5_export"),
        help="Directory where CSV files and manifest.json will be written.",
    )
    parser.add_argument(
        "--env",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env file with SB_SYMBOLS, SB_TIMEFRAMES, and SB_IMPORT_START.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(args.env, require_database_url=False)

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 package is not installed in this Python environment.")
        print(f'Run: "{sys.executable}" -m pip install -r requirements-win-mt5.txt')
        return 1

    timeframe_map = {
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

    if not mt5.initialize():
        print(f"MT5 initialize failed: {mt5.last_error()}")
        print("Open MetaTrader 5 and log in to your broker account, then retry.")
        return 2

    date_from = utc_datetime_from_date(config.import_start)
    date_to = datetime.now(timezone.utc)
    exported_files: list[dict] = []
    total_rows = 0

    try:
        for symbol in config.symbols:
            if not mt5.symbol_select(symbol, True):
                print(f"SKIP {symbol}: symbol_select failed: {mt5.last_error()}")
                continue

            for timeframe in config.timeframes:
                mt5_timeframe = timeframe_map.get(timeframe)
                if mt5_timeframe is None:
                    print(f"SKIP {symbol} {timeframe}: unsupported timeframe")
                    continue

                rates = mt5.copy_rates_range(symbol, mt5_timeframe, date_from, date_to)
                candles = normalize_rates(rates, symbol=symbol, timeframe=timeframe)

                safe_symbol = "".join(ch if ch.isalnum() else "_" for ch in symbol)
                filename = f"{safe_symbol}_{timeframe}_{config.import_start.isoformat()}_to_now.csv.gz"
                output_path = output_dir / filename
                candles.to_csv(output_path, index=False, compression="gzip")

                row_count = len(candles)
                total_rows += row_count
                exported_files.append(
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "rows": row_count,
                        "path": str(output_path),
                    }
                )
                print(f"{symbol:12} {timeframe:4} {row_count:8} candles -> {output_path}")
    finally:
        mt5.shutdown()

    manifest = {
        "source": "mt5",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "symbols": config.symbols,
        "timeframes": config.timeframes,
        "total_rows": total_rows,
        "files": exported_files,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Total exported rows: {total_rows}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.market_data import (
    check_connection,
    create_db_engine,
    create_schema,
    fetch_candle_summary,
    load_config,
    upsert_candles,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import MT5 candle CSV exports into PostgreSQL."
    )
    parser.add_argument(
        "input",
        help="CSV/CSV.GZ file or directory containing MT5 candle exports.",
    )
    parser.add_argument(
        "--env",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env file with DATABASE_URL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    files = list(_find_csv_files(input_path))

    if not files:
        print(f"No CSV files found under: {input_path}")
        return 1

    config = load_config(args.env)
    if not config.database_url:
        print("DATABASE_URL is required for CSV import.")
        return 1

    engine = create_db_engine(config.database_url)
    create_schema(engine)

    print(check_connection(engine).to_string(index=False))

    total_rows = 0
    for file_path in files:
        candles = pd.read_csv(file_path)
        rows = upsert_candles(engine, candles)
        total_rows += rows
        print(f"{rows:8} candles <- {file_path}")

    print(f"Total imported rows: {total_rows}")
    print(fetch_candle_summary(engine).to_string(index=False))
    return 0


def _find_csv_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]

    return sorted(
        [
            path
            for path in input_path.rglob("*")
            if path.is_file() and (path.name.endswith(".csv") or path.name.endswith(".csv.gz"))
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())

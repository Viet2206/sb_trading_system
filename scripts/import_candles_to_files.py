from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.file_store import fetch_file_candle_summary, upsert_file_candles
from sb_system.market_data import load_config, utc_datetime_from_date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import broker candle CSV exports into the local file store."
    )
    parser.add_argument(
        "input",
        help="CSV/CSV.GZ file or directory containing broker candle exports.",
    )
    parser.add_argument(
        "--env",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env file with SB_DATA_DIR and SB_FILE_FORMAT.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    files = list(_find_csv_files(input_path))

    if not files:
        print(f"No CSV files found under: {input_path}")
        return 1

    config = load_config(args.env, require_database_url=False)

    total_rows = 0
    for file_path in files:
        candles = pd.read_csv(file_path)
        rows = upsert_file_candles(
            config.data_dir,
            candles,
            file_format=config.file_format,
            retain_from=utc_datetime_from_date(config.import_start),
        )
        total_rows += rows
        print(f"{rows:8} candles <- {file_path}")

    print(f"Total imported rows: {total_rows}")
    summary = fetch_file_candle_summary(config.data_dir, file_format=config.file_format)
    print(summary.to_string(index=False) if not summary.empty else "No candles in file store.")
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

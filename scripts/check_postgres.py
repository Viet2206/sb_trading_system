from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.market_data import (
    check_connection,
    create_db_engine,
    create_schema,
    fetch_candle_summary,
    load_config,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify PostgreSQL connectivity and apply pending SB schema migrations."
    )
    parser.add_argument(
        "--env",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env file with DATABASE_URL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.env)
        engine = create_db_engine(config.database_url or "")
        started = perf_counter()
        create_schema(engine)
        connection = check_connection(engine).iloc[0]
        summary = fetch_candle_summary(engine)
        elapsed_ms = (perf_counter() - started) * 1_000
    except Exception as exc:
        print(f"PostgreSQL check failed: {exc}")
        print("Confirm PostgreSQL is running and DATABASE_URL in .env is correct.")
        return 1
    finally:
        if "engine" in locals():
            engine.dispose()

    print(
        f"PostgreSQL ready: database={connection['database']} "
        f"user={connection['username']} schema=current ({elapsed_ms:.0f} ms)"
    )
    print(f"Market series indexed: {len(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

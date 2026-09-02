from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.market_data import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a compressed PostgreSQL backup.")
    parser.add_argument("--env", default=str(PROJECT_ROOT / ".env"))
    parser.add_argument("--output", help="Optional output .dump path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.env)
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        print("pg_dump was not found. Install PostgreSQL client tools and add them to PATH.")
        return 1

    output = (
        Path(args.output)
        if args.output
        else PROJECT_ROOT
        / "data"
        / "backups"
        / f"sb_system_{datetime.now(UTC):%Y%m%d_%H%M%S}.dump"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    database = make_url(config.database_url or "")
    command = [pg_dump]
    if database.host:
        command.extend(["--host", database.host])
    if database.port:
        command.extend(["--port", str(database.port)])
    if database.username:
        command.extend(["--username", database.username])
    command.extend(
        [
            "--dbname",
            database.database or "",
            "--format=custom",
            "--file",
            str(output),
        ]
    )
    process_env = os.environ.copy()
    if database.password:
        process_env["PGPASSWORD"] = database.password
    result = subprocess.run(
        command,
        check=False,
        env=process_env,
    )
    if result.returncode != 0:
        print("PostgreSQL backup failed. Verify DATABASE_URL and pg_dump.")
        return result.returncode
    print(f"Backup created: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

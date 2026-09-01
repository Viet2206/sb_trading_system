from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.file_store import rebuild_file_candle_summary
from sb_system.market_data import load_config


def main() -> int:
    config = load_config(require_database_url=False)
    if config.storage != "file":
        print("Market summary rebuild is only needed when SB_STORAGE=file.")
        return 0
    summary = rebuild_file_candle_summary(config.data_dir, file_format=config.file_format)
    print(f"Indexed {len(summary)} symbol/timeframe candle files in {config.data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

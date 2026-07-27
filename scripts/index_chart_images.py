from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.image_matching import ChartImageIndex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract historical chart images and build the local visual index."
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Discard the existing visual index and rebuild every chart image.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    result = ChartImageIndex().build(rebuild=parse_args().rebuild)
    print(json.dumps(result, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SB System backend API.")
    parser.add_argument("--host", default="127.0.0.1", help="API bind host.")
    parser.add_argument("--port", default=8000, type=int, help="API bind port.")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload mode.")
    return parser.parse_args()


def main() -> int:
    import uvicorn

    args = parse_args()
    uvicorn.run(
        "sb_system.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(PROJECT_ROOT / "src"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


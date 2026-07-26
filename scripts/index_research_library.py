from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sb_system.research import ResearchLibrary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index Stacey Burke PDF documents for local search and RAG."
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the existing research index before processing all PDFs.",
    )
    args = parser.parse_args()

    result = ResearchLibrary().index_documents(rebuild=args.rebuild)
    print(json.dumps(result, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

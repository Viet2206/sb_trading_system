from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from sb_system.daily_checklist import build_daily_checklist, load_checklist_state, save_checklist_state


class DailyChecklistTests(unittest.TestCase):
    def test_build_daily_checklist_ranks_signal_candidates(self) -> None:
        data = {
            "XAUUSD": _daily(
                [
                    (100, 101, 95, 96),
                    (96, 98, 92, 93),
                    (93, 99, 91, 98),
                ]
            ),
            "EURUSD": _daily(
                [
                    (100, 105, 99, 104),
                    (104, 108, 103, 107),
                    (107, 109, 101, 102),
                ]
            ),
            "AUDUSD": _daily(
                [
                    (100, 104, 98, 102),
                    (102, 103, 99, 101),
                    (101, 102, 100, 101.5),
                ]
            ),
        }

        checklist = build_daily_checklist(
            object(),
            symbols=["XAUUSD", "EURUSD", "AUDUSD"],
            fetcher=lambda _source, symbol, **_kwargs: data[symbol],
        )

        rows = {row["symbol"]: row for row in checklist["rows"]}
        self.assertIn("FGD", rows["XAUUSD"]["signal_days"])
        self.assertEqual(rows["XAUUSD"]["candidate_direction"], "Buy")
        self.assertIn("FRD", rows["EURUSD"]["signal_days"])
        self.assertEqual(rows["EURUSD"]["candidate_direction"], "Sell")
        self.assertGreater(rows["XAUUSD"]["quality_score"], rows["AUDUSD"]["quality_score"])

    def test_checklist_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_checklist.json"
            saved = save_checklist_state(
                {
                    "date": "2026-07-17",
                    "symbol": "XAUUSD",
                    "checks": {"major_news_clear": True},
                    "journal": {"did_trade": "yes", "result": "+50"},
                },
                path=path,
            )
            loaded = load_checklist_state("2026-07-17", path=path)

        self.assertEqual(saved, loaded)
        self.assertEqual(loaded["symbol"], "XAUUSD")
        self.assertTrue(loaded["checks"]["major_news_clear"])
        self.assertEqual(loaded["journal"]["result"], "+50")


def _daily(candles: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    start = datetime(2026, 7, 13, tzinfo=UTC)
    rows: list[dict[str, Any]] = []
    for index, (open_, high, low, close) in enumerate(candles):
        rows.append(
            {
                "broker_symbol": "TEST",
                "timeframe": "D1",
                "candle_time": pd.Timestamp(start + timedelta(days=index)),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "tick_volume": 0,
                "spread": 0,
                "real_volume": 0,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()

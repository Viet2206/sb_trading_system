from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

import pandas as pd

from sb_system.context import _classify_day


class DailySetupLabelTests(unittest.TestCase):
    def test_first_green_day_requires_two_prior_red_days(self) -> None:
        daily = _daily(
            [
                ("red", 100, 101, 95, 96),
                ("red", 96, 98, 92, 93),
                ("green", 93, 99, 91, 98),
                ("red", 98, 100, 94, 95),
                ("green", 95, 101, 93, 100),
            ]
        )

        self.assertIn("FGD", _classify_day(daily, 2))
        self.assertNotIn("FGD", _classify_day(daily, 4))

    def test_first_red_day_requires_two_prior_green_days(self) -> None:
        daily = _daily(
            [
                ("green", 100, 105, 99, 104),
                ("green", 104, 108, 103, 107),
                ("red", 107, 109, 101, 102),
                ("green", 102, 106, 100, 105),
                ("red", 105, 106, 99, 100),
            ]
        )

        self.assertIn("FRD", _classify_day(daily, 2))
        self.assertNotIn("FRD", _classify_day(daily, 4))

    def test_three_day_labels_only_mark_third_consecutive_day(self) -> None:
        daily = _daily(
            [
                ("red", 100, 101, 95, 96),
                ("green", 96, 101, 95, 100),
                ("green", 100, 105, 99, 104),
                ("green", 104, 108, 103, 107),
                ("green", 107, 111, 106, 110),
                ("red", 110, 112, 104, 105),
                ("red", 105, 106, 100, 101),
                ("red", 101, 102, 96, 97),
                ("red", 97, 99, 93, 94),
            ]
        )

        self.assertNotIn("3DL", _classify_day(daily, 2))
        self.assertIn("3DL", _classify_day(daily, 3))
        self.assertNotIn("3DL", _classify_day(daily, 4))
        self.assertNotIn("3DS", _classify_day(daily, 6))
        self.assertIn("3DS", _classify_day(daily, 7))
        self.assertNotIn("3DS", _classify_day(daily, 8))


def _daily(candles: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for index, (_, open_, high, low, close) in enumerate(candles):
        rows.append(
            {
                "candle_time": pd.Timestamp(start + timedelta(days=index)),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    unittest.main()

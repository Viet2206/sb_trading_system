from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from sb_system.ctrader import chunk_ranges, normalize_trendbars


class CTraderTests(unittest.TestCase):
    def test_normalize_trendbars_converts_relative_ohlc(self) -> None:
        trendbar = SimpleNamespace(
            utcTimestampInMinutes=int(datetime(2026, 1, 2, 3, 15, tzinfo=UTC).timestamp() / 60),
            low=100000,
            deltaOpen=500,
            deltaHigh=1500,
            deltaClose=800,
            volume=42,
        )

        candles = normalize_trendbars([trendbar], symbol="XAUUSD", timeframe="M15", digits=5)

        self.assertEqual(len(candles), 1)
        row = candles.iloc[0]
        self.assertEqual(row["broker_symbol"], "XAUUSD")
        self.assertEqual(row["timeframe"], "M15")
        self.assertEqual(row["candle_time"].to_pydatetime(), datetime(2026, 1, 2, 3, 15, tzinfo=UTC))
        self.assertEqual(row["open"], 1.005)
        self.assertEqual(row["high"], 1.015)
        self.assertEqual(row["low"], 1.0)
        self.assertEqual(row["close"], 1.008)
        self.assertEqual(row["tick_volume"], 42)

    def test_chunk_ranges_splits_large_requests(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        end = datetime(2026, 1, 10, tzinfo=UTC)

        ranges = chunk_ranges(start, end, timeframe="M1", chunk_days={"M1": 3})

        self.assertEqual(len(ranges), 3)
        self.assertEqual(ranges[0], (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 4, tzinfo=UTC)))
        self.assertEqual(ranges[-1][1], end)


if __name__ == "__main__":
    unittest.main()

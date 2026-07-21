from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from sb_system.file_store import (
    fetch_file_candle_summary,
    fetch_file_candles,
    fetch_file_symbols,
    upsert_file_candles,
)


class FileStoreTests(unittest.TestCase):
    def test_upsert_and_fetch_file_candles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            initial = pd.DataFrame(
                [
                    _candle("XAUUSD+", "M15", "2026-01-01T00:00:00Z", close=100.0),
                    _candle("XAUUSD+", "M15", "2026-01-01T00:15:00Z", close=101.0),
                ]
            )
            replacement = pd.DataFrame(
                [
                    _candle("XAUUSD+", "M15", "2026-01-01T00:15:00Z", close=102.0),
                    _candle("XAUUSD+", "M15", "2026-01-01T00:30:00Z", close=103.0),
                ]
            )

            self.assertEqual(upsert_file_candles(data_dir, initial), 2)
            self.assertEqual(upsert_file_candles(data_dir, replacement), 2)

            candles = fetch_file_candles(data_dir, symbol="XAUUSD+", timeframe="M15")
            self.assertEqual(len(candles), 3)
            self.assertEqual(candles.iloc[1]["close"], 102.0)

            latest_two = fetch_file_candles(data_dir, symbol="XAUUSD+", timeframe="M15", limit=2)
            self.assertEqual(len(latest_two), 2)
            self.assertEqual(latest_two.iloc[0]["close"], 102.0)

            summary = fetch_file_candle_summary(data_dir)
            self.assertEqual(summary.iloc[0]["broker_symbol"], "XAUUSD+")
            self.assertEqual(summary.iloc[0]["timeframe"], "M15")
            self.assertEqual(summary.iloc[0]["candles"], 3)

            symbols = fetch_file_symbols(data_dir)
            self.assertEqual(symbols.iloc[0]["broker_symbol"], "XAUUSD+")
            self.assertEqual(symbols.iloc[0]["candles"], 3)


def _candle(symbol: str, timeframe: str, candle_time: str, *, close: float) -> dict:
    return {
        "broker_symbol": symbol,
        "timeframe": timeframe,
        "candle_time": candle_time,
        "open": close - 1.0,
        "high": close + 1.0,
        "low": close - 2.0,
        "close": close,
        "tick_volume": 10,
        "spread": 1,
        "real_volume": 0,
    }


if __name__ == "__main__":
    unittest.main()

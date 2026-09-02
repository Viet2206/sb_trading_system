from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from sb_system.file_store import (
    SUMMARY_INDEX_NAME,
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
            self.assertTrue((data_dir / SUMMARY_INDEX_NAME).exists())
            self.assertEqual(list(data_dir.rglob("*.tmp")), [])

            with patch("sb_system.file_store._read_candles", side_effect=AssertionError("summary scanned candles")):
                cached_summary = fetch_file_candle_summary(data_dir)
            self.assertEqual(cached_summary.iloc[0]["candles"], 3)

    def test_atomic_replacement_invalidates_cached_candles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            self.assertEqual(
                upsert_file_candles(
                    data_dir,
                    pd.DataFrame([_candle("EURUSD", "M5", "2026-06-01T00:00:00Z", close=1.1)]),
                ),
                1,
            )
            first = fetch_file_candles(data_dir, symbol="EURUSD", timeframe="M5")
            self.assertEqual(first.iloc[0]["close"], 1.1)

            upsert_file_candles(
                data_dir,
                pd.DataFrame([_candle("EURUSD", "M5", "2026-06-01T00:00:00Z", close=1.2)]),
            )
            refreshed = fetch_file_candles(data_dir, symbol="EURUSD", timeframe="M5")
            self.assertEqual(refreshed.iloc[0]["close"], 1.2)
            self.assertEqual(list(data_dir.rglob("*.tmp")), [])

    def test_retention_window_prunes_older_candles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            rows = pd.DataFrame(
                [
                    _candle("XAUUSD.pc", "M5", "2026-05-31T23:55:00Z", close=100.0),
                    _candle("XAUUSD.pc", "M5", "2026-06-01T00:00:00Z", close=101.0),
                    _candle("XAUUSD.pc", "M5", "2026-09-10T00:00:00Z", close=102.0),
                ]
            )
            upsert_file_candles(
                data_dir,
                rows,
                retain_from=pd.Timestamp("2026-06-01T00:00:00Z").to_pydatetime(),
            )

            candles = fetch_file_candles(data_dir, symbol="XAUUSD.pc", timeframe="M5")
            self.assertEqual(len(candles), 2)
            self.assertEqual(candles.iloc[0]["candle_time"], pd.Timestamp("2026-06-01T00:00:00Z"))


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

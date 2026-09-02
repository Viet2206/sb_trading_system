from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from fastapi.testclient import TestClient

from sb_system.api import app, get_config
from sb_system.file_store import upsert_file_candles
from sb_system.market_data import ImportConfig


class APITests(unittest.TestCase):
    def test_vite_fallback_port_is_allowed_by_cors(self) -> None:
        response = TestClient(app).options(
            "/runtime/settings",
            headers={
                "Origin": "http://127.0.0.1:5175",
                "Access-Control-Request-Method": "PUT",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5175",
        )

    def test_candle_endpoint_defaults_to_three_calendar_month_window(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            rows = pd.DataFrame(
                [
                    _candle("2026-05-31T23:55:00Z", 100.0),
                    _candle("2026-06-01T00:00:00Z", 101.0),
                    _candle("2026-09-10T00:00:00Z", 102.0),
                ]
            )
            upsert_file_candles(data_dir, rows)
            config = ImportConfig(
                database_url=None,
                storage="file",
                data_dir=data_dir,
                file_format="csv.gz",
                symbols=["XAUUSD.pc"],
                timeframes=["M5"],
                import_start=date(2026, 6, 1),
            )
            app.dependency_overrides[get_config] = lambda: config
            try:
                response = TestClient(app).get(
                    "/candles",
                    params={
                        "symbol": "XAUUSD.pc",
                        "timeframe": "M5",
                        "end": "2026-09-10T23:59:59Z",
                    },
                )
            finally:
                app.dependency_overrides.pop(get_config, None)

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["count"], 2)
            self.assertEqual(
                pd.Timestamp(payload["candles"][0]["candle_time"]),
                pd.Timestamp("2026-06-01T00:00:00Z"),
            )


def _candle(candle_time: str, close: float) -> dict:
    return {
        "broker_symbol": "XAUUSD.pc",
        "timeframe": "M5",
        "candle_time": candle_time,
        "open": close - 1,
        "high": close + 1,
        "low": close - 2,
        "close": close,
        "tick_volume": 10,
        "spread": 1,
        "real_volume": 0,
    }


if __name__ == "__main__":
    unittest.main()

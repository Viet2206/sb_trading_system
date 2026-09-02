from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import sb_system.api as api_module
from sb_system.api import app, get_config
from sb_system.market_data import (
    ImportConfig,
    create_db_engine,
    create_schema,
    fetch_candle_summary,
    fetch_candles,
    fetch_symbols,
    latest_candle_time,
    prune_candles_before,
    upsert_candles,
)


TEST_DATABASE_URL = os.getenv("SB_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set SB_TEST_DATABASE_URL to run PostgreSQL integration tests.",
)


@pytest.fixture()
def engine():
    database_engine = create_db_engine(TEST_DATABASE_URL or "")
    with database_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS market CASCADE"))
    create_schema(database_engine)
    yield database_engine
    database_engine.dispose()


def _candles() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "broker_symbol": "EURUSD",
                "timeframe": "M5",
                "candle_time": "2026-05-31T23:55:00Z",
                "open": 1.1,
                "high": 1.2,
                "low": 1.0,
                "close": 1.15,
                "tick_volume": 10,
                "spread": 2,
                "real_volume": 0,
            },
            {
                "broker_symbol": "EURUSD",
                "timeframe": "M5",
                "candle_time": "2026-06-01T00:00:00Z",
                "open": 1.15,
                "high": 1.25,
                "low": 1.1,
                "close": 1.2,
                "tick_volume": 11,
                "spread": 2,
                "real_volume": 0,
            },
            {
                "broker_symbol": "EURUSD",
                "timeframe": "M5",
                "candle_time": "2026-06-01T00:05:00Z",
                "open": 1.2,
                "high": 1.3,
                "low": 1.15,
                "close": 1.25,
                "tick_volume": 12,
                "spread": 2,
                "real_volume": 0,
            },
        ]
    )


def test_schema_bulk_upsert_summary_and_retention(engine) -> None:
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    assert upsert_candles(engine, _candles(), source="mt5", retain_from=cutoff) == 3

    summary = fetch_candle_summary(engine)
    assert len(summary) == 1
    assert int(summary.iloc[0]["candles"]) == 2
    assert pd.Timestamp(summary.iloc[0]["first_candle"]) == pd.Timestamp(cutoff)
    assert latest_candle_time(engine, symbol="EURUSD", timeframe="M5") == pd.Timestamp(
        "2026-06-01T00:05:00Z"
    )

    update = _candles().iloc[[2]].copy()
    update.loc[:, "close"] = 1.29
    assert upsert_candles(engine, update, source="mt5", retain_from=cutoff) == 1
    fetched = fetch_candles(engine, symbol="EURUSD", timeframe="M5", limit=10)
    assert len(fetched) == 2
    assert float(fetched.iloc[-1]["close"]) == pytest.approx(1.29)
    assert int(fetch_symbols(engine).iloc[0]["candles"]) == 2

    assert prune_candles_before(engine, datetime(2026, 6, 1, 0, 5, tzinfo=UTC)) == 1
    assert int(fetch_candle_summary(engine).iloc[0]["candles"]) == 1


def test_schema_migrations_are_idempotent(engine) -> None:
    create_schema(engine)
    with engine.connect() as conn:
        versions = conn.execute(
            text("SELECT version FROM market.schema_migrations ORDER BY version")
        ).scalars().all()
    assert versions == ["001_market_data", "002_market_data_performance"]


def test_postgres_api_endpoints_return_candles_without_scanning_files(engine, monkeypatch) -> None:
    cutoff = datetime(2026, 6, 1, tzinfo=UTC)
    upsert_candles(engine, _candles(), source="mt5", retain_from=cutoff)
    config = ImportConfig(
        database_url=TEST_DATABASE_URL,
        storage="postgres",
        data_dir=Path("unused"),
        file_format="csv.gz",
        symbols=["EURUSD"],
        timeframes=["M5"],
        import_start=date(2026, 6, 1),
    )
    app.dependency_overrides[get_config] = lambda: config
    monkeypatch.setattr(api_module, "get_engine", lambda: engine)
    try:
        client = TestClient(app)
        health = client.get("/health")
        summary = client.get("/candles/summary")
        candles = client.get(
            "/candles",
            params={
                "symbol": "EURUSD",
                "timeframe": "M5",
                "start": "2026-06-01T00:00:00Z",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert health.status_code == 200
    assert health.json()["storage"] == "postgres"
    assert summary.status_code == 200
    assert summary.json()[0]["candles"] == 2
    assert candles.status_code == 200
    assert candles.json()["count"] == 2

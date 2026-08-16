from __future__ import annotations

import pandas as pd

from sb_system.context import _build_levels


def test_month_levels_use_previous_month_and_first_trading_day() -> None:
    daily = pd.DataFrame(
        [
            _candle("2026-07-30", high=108, low=96),
            _candle("2026-07-31", high=112, low=94),
            _candle("2026-08-03", high=105, low=97),
            _candle("2026-08-04", high=109, low=99),
            _candle("2026-08-10", high=110, low=101),
        ]
    )
    chart_end = pd.Timestamp("2026-08-10T23:00:00Z")

    levels = _build_levels(daily, chart_end)
    by_key = {level["key"]: level for level in levels}

    assert by_key["previous_month_high"]["price"] == 112
    assert by_key["previous_month_low"]["price"] == 94
    assert by_key["previous_month_high"]["start_time"] == "2026-08-01T00:00:00+00:00"
    assert by_key["previous_month_low"]["start_time"] == "2026-08-01T00:00:00+00:00"

    assert by_key["current_month_first_day_high"]["price"] == 105
    assert by_key["current_month_first_day_low"]["price"] == 97
    assert by_key["current_month_first_day_high"]["start_time"] == "2026-08-03T00:00:00+00:00"
    assert by_key["current_month_first_day_low"]["start_time"] == "2026-08-03T00:00:00+00:00"


def test_month_levels_are_omitted_without_required_daily_data() -> None:
    daily = pd.DataFrame([_candle("2026-08-03", high=105, low=97)])
    chart_end = pd.Timestamp("2026-08-03T23:00:00Z")

    levels = _build_levels(daily, chart_end)
    keys = {level["key"] for level in levels}

    assert "previous_month_high" not in keys
    assert "previous_month_low" not in keys
    assert "current_month_first_day_high" in keys
    assert "current_month_first_day_low" in keys


def _candle(
    candle_time: str,
    *,
    high: float,
    low: float,
    open_price: float = 100,
    close: float = 101,
) -> dict[str, object]:
    return {
        "candle_time": pd.Timestamp(candle_time, tz="UTC"),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
    }

from __future__ import annotations

import pandas as pd

from sb_system.context import _build_cib_markers, _is_closing_inside_breakout


def test_closing_inside_breakout_requires_range_break_and_inside_close() -> None:
    daily = pd.DataFrame(
        [
            _candle("2026-07-13", open_price=100, high=110, low=90, close=105),
            _candle("2026-07-14", open_price=108, high=115, low=95, close=104),
            _candle("2026-07-15", open_price=104, high=109, low=96, close=103),
            _candle("2026-07-16", open_price=103, high=112, low=97, close=111),
        ]
    )

    assert _is_closing_inside_breakout(daily, 1)
    assert not _is_closing_inside_breakout(daily, 2)
    assert not _is_closing_inside_breakout(daily, 3)


def test_previous_day_cib_creates_marker_for_current_day_boundary() -> None:
    daily = pd.DataFrame(
        [
            _candle("2026-07-13", open_price=100, high=110, low=90, close=105),
            _candle("2026-07-14", open_price=108, high=115, low=95, close=104),
            _candle("2026-07-15", open_price=104, high=109, low=96, close=103),
        ]
    )
    chart = pd.DataFrame(
        [
            _candle("2026-07-14 00:00", open_price=108, high=109, low=107, close=108),
            _candle("2026-07-15 00:00", open_price=104, high=105, low=103, close=104),
            _candle("2026-07-15 00:15", open_price=104, high=106, low=103, close=105),
        ]
    )

    markers = _build_cib_markers(chart, daily)

    assert markers == [
        {
            "id": "cib-2026-07-15",
            "time": "2026-07-15T00:00:00+00:00",
            "open": 108.0,
            "close": 104.0,
            "direction": "red",
            "color": "#ef4444",
        }
    ]


def _candle(
    candle_time: str,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> dict[str, object]:
    return {
        "candle_time": pd.Timestamp(candle_time, tz="UTC"),
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
    }

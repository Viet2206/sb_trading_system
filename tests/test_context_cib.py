from __future__ import annotations

import pandas as pd

from sb_system.context import _build_cib_markers, _closing_breakout_direction


def test_close_in_breakout_requires_close_outside_previous_range() -> None:
    daily = pd.DataFrame(
        [
            _candle("2026-07-13", open_price=100, high=110, low=90, close=105),
            _candle("2026-07-14", open_price=108, high=115, low=95, close=111),
            _candle("2026-07-15", open_price=111, high=113, low=85, close=94),
            _candle("2026-07-16", open_price=94, high=112, low=92, close=100),
        ]
    )

    assert _closing_breakout_direction(daily, 1) == "green"
    assert _closing_breakout_direction(daily, 2) == "red"
    assert _closing_breakout_direction(daily, 3) is None


def test_xauusd_markers_match_reviewed_current_days() -> None:
    daily = pd.DataFrame(
        [
            _candle("2026-07-10", open_price=4125.72, high=4134.83, low=4073.62, close=4119.87),
            _candle("2026-07-13", open_price=4096.66, high=4103.46, low=3986.61, close=4002.01),
            _candle("2026-07-14", open_price=4005.56, high=4103.24, low=3983.57, close=4052.66),
            _candle("2026-07-15", open_price=4053.35, high=4081.21, low=4017.43, close=4060.01),
            _candle("2026-07-16", open_price=4064.95, high=4066.75, low=3969.29, close=3976.46),
            _candle("2026-07-17", open_price=3978.36, high=4023.76, low=3959.70, close=4018.34),
        ]
    )
    chart = pd.DataFrame(
        [
            _candle("2026-07-14 01:00", open_price=4005.56, high=4008, low=3998, close=4003),
            _candle("2026-07-15 01:00", open_price=4053.35, high=4056, low=4048, close=4051),
            _candle("2026-07-17 01:00", open_price=3978.36, high=3982, low=3973, close=3979),
        ]
    )

    markers = _build_cib_markers(chart, daily)

    assert [marker["id"] for marker in markers] == [
        "cib-2026-07-14",
        "cib-2026-07-17",
    ]
    assert all(marker["direction"] == "red" for marker in markers)
    assert all(marker["color"] == "#ef4444" for marker in markers)


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

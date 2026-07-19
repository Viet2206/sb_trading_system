from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

import pandas as pd
from sqlalchemy.engine import Engine

from sb_system.market_data import fetch_candles


OVERLAY_LINE_COLOR = "#64748b"
SESSION_FILL_COLOR = "#94a3b8"

SESSION_WINDOWS = [
    ("asia", "Asia", time(3, 0), time(6, 0), SESSION_FILL_COLOR),
    ("london", "London", time(9, 0), time(12, 0), SESSION_FILL_COLOR),
    ("new_york", "New York", time(15, 0), time(18, 0), SESSION_FILL_COLOR),
]


def build_sb_overlays(
    engine: Engine,
    *,
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    chart_candles = fetch_candles(
        engine,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
    )
    daily_candles = fetch_candles(engine, symbol=symbol, timeframe="D1", limit=420)

    if chart_candles.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "levels": [],
            "sessions": [],
            "day_periods": [],
            "month_separators": [],
            "day_range_pipes": [],
            "day_close_segments": [],
            "day_labels": [],
            "setup_labels": [],
            "notes": ["No chart candles available for the requested symbol/timeframe."],
        }

    chart = _prepare_candles(chart_candles)
    daily = _prepare_candles(daily_candles)
    chart_start = chart["candle_time"].min()
    chart_end = chart["candle_time"].max()
    apply_intraday_template = timeframe not in {"H4", "D1"}

    levels = _build_levels(
        daily,
        chart_end,
        include_previous_day_close=not apply_intraday_template,
        include_previous_day_range=not apply_intraday_template,
    )
    sessions = _build_sessions(chart, chart_start, chart_end) if apply_intraday_template else []
    day_periods = _build_day_periods(chart) if apply_intraday_template else []
    month_separators = _build_month_separators(chart)
    day_range_pipes = _build_day_range_pipes(chart, daily) if apply_intraday_template else []
    day_close_segments = _build_day_close_segments(chart, daily) if apply_intraday_template else []
    day_labels, setup_labels = _build_day_labels(daily, chart_start, chart_end)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "levels": levels,
        "sessions": sessions,
        "day_periods": day_periods,
        "month_separators": month_separators,
        "day_range_pipes": day_range_pipes,
        "day_close_segments": day_close_segments,
        "day_labels": day_labels,
        "setup_labels": setup_labels,
        "notes": [
            "FGD, FRD, 3DL, and 3DS are v0 deterministic labels and should be refined against the SB playbook examples.",
            "Session windows use chart/data time: Asia 03:00-06:00, London 09:00-12:00, New York 15:00-18:00.",
            "Intraday day-period and session templates are hidden on H4 and D1 charts.",
            "Horizontal context levels are solid right-extending rays from their relevant start time.",
            "Intraday previous-day high/low levels are drawn as connected range pipes.",
        ],
    }


def _prepare_candles(candles: pd.DataFrame) -> pd.DataFrame:
    prepared = candles.copy()
    prepared["candle_time"] = pd.to_datetime(prepared["candle_time"], utc=True)
    return prepared.sort_values("candle_time").reset_index(drop=True)


def _build_levels(
    daily: pd.DataFrame,
    chart_end: pd.Timestamp,
    *,
    include_previous_day_close: bool = True,
    include_previous_day_range: bool = True,
) -> list[dict[str, Any]]:
    if daily.empty:
        return []

    current_day = chart_end.date()
    current_day_start = datetime.combine(current_day, time(0, 0), tzinfo=UTC)
    previous_days = daily[daily["candle_time"].dt.date < current_day]
    levels: list[dict[str, Any]] = []

    if not previous_days.empty:
        previous_day = previous_days.iloc[-1]
        if include_previous_day_range:
            levels.extend(
                [
                    _level("previous_day_high", "PDH", previous_day["high"], OVERLAY_LINE_COLOR, current_day_start),
                    _level("previous_day_low", "PDL", previous_day["low"], OVERLAY_LINE_COLOR, current_day_start),
                ]
            )
        if include_previous_day_close:
            levels.append(_level("previous_day_close", "PDC", previous_day["close"], OVERLAY_LINE_COLOR, current_day_start))

    week_start = _week_start(chart_end)
    previous_week = _previous_week_slice(daily, chart_end)
    if not previous_week.empty:
        levels.extend(
            [
                _level("previous_week_high", "PWH", previous_week["high"].max(), OVERLAY_LINE_COLOR, week_start),
                _level("previous_week_low", "PWL", previous_week["low"].min(), OVERLAY_LINE_COLOR, week_start),
            ]
        )

    friday = _latest_friday(daily, chart_end)
    if friday is not None:
        levels.append(_level("friday_close", "Fri Close", friday["close"], OVERLAY_LINE_COLOR, friday["candle_time"]))

    monday = _current_week_monday(daily, chart_end)
    if monday is not None:
        levels.extend(
            [
                _level("current_monday_high", "Mon High", monday["high"], OVERLAY_LINE_COLOR, monday["candle_time"]),
                _level("current_monday_low", "Mon Low", monday["low"], OVERLAY_LINE_COLOR, monday["candle_time"]),
            ]
        )

    return levels


def _build_sessions(
    chart: pd.DataFrame,
    chart_start: pd.Timestamp,
    chart_end: pd.Timestamp,
) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    current_date = chart_start.date()
    end_date = chart_end.date()

    while current_date <= end_date:
        for session_id, label, start_time, end_time, color in SESSION_WINDOWS:
            start_dt = datetime.combine(current_date, start_time, tzinfo=UTC)
            end_dt = datetime.combine(current_date, end_time, tzinfo=UTC)
            session_slice = chart[
                (chart["candle_time"] >= start_dt)
                & (chart["candle_time"] < end_dt)
            ]

            if not session_slice.empty:
                first_time = session_slice.iloc[0]["candle_time"].to_pydatetime()
                last_time = session_slice.iloc[-1]["candle_time"].to_pydatetime()
                sessions.append(
                    {
                        "id": f"{session_id}-{current_date.isoformat()}",
                        "label": label,
                        "start_time": first_time.isoformat(),
                        "end_time": last_time.isoformat(),
                        "high": float(session_slice["high"].max()),
                        "low": float(session_slice["low"].min()),
                        "color": color,
                    }
                )

        current_date += timedelta(days=1)

    return sessions


def _build_day_periods(chart: pd.DataFrame) -> list[dict[str, Any]]:
    periods: list[dict[str, Any]] = []

    for index, (day, day_slice) in enumerate(chart.groupby(chart["candle_time"].dt.date)):
        first_time = day_slice.iloc[0]["candle_time"].to_pydatetime()
        last_time = day_slice.iloc[-1]["candle_time"].to_pydatetime()
        label_time = pd.Timestamp(first_time)

        periods.append(
            {
                "id": f"day-{day.isoformat()}",
                "label": label_time.strftime("%a"),
                "start_time": first_time.isoformat(),
                "end_time": last_time.isoformat(),
                "kind": "day_period",
                "variant": "even" if index % 2 == 0 else "odd",
            }
        )

    return periods


def _build_month_separators(chart: pd.DataFrame) -> list[dict[str, Any]]:
    separators: list[dict[str, Any]] = []
    previous_month: tuple[int, int] | None = None

    for _, row in chart.iterrows():
        candle_time = row["candle_time"]
        month_key = (candle_time.year, candle_time.month)
        if previous_month is not None and month_key != previous_month:
            separators.append(
                {
                    "id": f"month-{candle_time.year}-{candle_time.month:02d}",
                    "time": candle_time.isoformat(),
                    "label": candle_time.strftime("%b"),
                }
            )
        previous_month = month_key

    return separators


def _build_day_range_pipes(chart: pd.DataFrame, daily: pd.DataFrame) -> list[dict[str, Any]]:
    if daily.empty:
        return []

    pipes: list[dict[str, Any]] = []
    day_slices = list(chart.groupby(chart["candle_time"].dt.date))

    for index, (day, day_slice) in enumerate(day_slices):
        previous_days = daily[daily["candle_time"].dt.date < day]
        if previous_days.empty:
            continue

        previous_day = previous_days.iloc[-1]
        first_time = day_slice.iloc[0]["candle_time"].to_pydatetime()
        if index + 1 < len(day_slices):
            _, next_day_slice = day_slices[index + 1]
            end_time = next_day_slice.iloc[0]["candle_time"].to_pydatetime()
        else:
            end_time = day_slice.iloc[-1]["candle_time"].to_pydatetime()

        pipes.append(
            {
                "id": f"pdh-pdl-{day.isoformat()}",
                "label": "PDH/PDL",
                "start_time": first_time.isoformat(),
                "end_time": end_time.isoformat(),
                "high": float(previous_day["high"]),
                "low": float(previous_day["low"]),
                "color": OVERLAY_LINE_COLOR,
            }
        )

    return pipes


def _build_day_close_segments(chart: pd.DataFrame, daily: pd.DataFrame) -> list[dict[str, Any]]:
    if daily.empty:
        return []

    segments: list[dict[str, Any]] = []

    for day, day_slice in chart.groupby(chart["candle_time"].dt.date):
        previous_days = daily[daily["candle_time"].dt.date < day]
        if previous_days.empty:
            continue

        previous_day = previous_days.iloc[-1]
        first_time = day_slice.iloc[0]["candle_time"].to_pydatetime()
        last_time = day_slice.iloc[-1]["candle_time"].to_pydatetime()

        segments.append(
            {
                "id": f"pdc-{day.isoformat()}",
                "label": "PDC",
                "start_time": first_time.isoformat(),
                "end_time": last_time.isoformat(),
                "price": float(previous_day["close"]),
                "color": OVERLAY_LINE_COLOR,
                "style": "solid",
            }
        )

    return segments


def _build_day_labels(
    daily: pd.DataFrame,
    chart_start: pd.Timestamp,
    chart_end: pd.Timestamp,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if daily.empty:
        return [], []

    visible_daily = daily[
        (daily["candle_time"] >= chart_start.floor("D"))
        & (daily["candle_time"] <= chart_end.ceil("D"))
    ].copy()

    day_labels: list[dict[str, Any]] = []
    setup_labels: list[dict[str, Any]] = []

    for index, row in visible_daily.iterrows():
        day_time = row["candle_time"]
        label_time = day_time + timedelta(hours=12)
        day_labels.append(
            {
                "time": label_time.isoformat(),
                "label": day_time.strftime("%a"),
                "kind": "day_of_week",
            }
        )

        labels = _classify_day(daily, index)
        for label in labels:
            setup_labels.append(
                {
                    "time": label_time.isoformat(),
                    "price": float(row["high"]),
                    "label": label,
                    "kind": _label_kind(label),
                }
            )

    return day_labels, setup_labels


def _classify_day(daily: pd.DataFrame, index: int) -> list[str]:
    labels: list[str] = []
    if index <= 0:
        return labels

    row = daily.loc[index]
    previous = daily.loc[index - 1]

    if row["high"] < previous["high"] and row["low"] > previous["low"]:
        labels.append("Inside Day")

    if row["close"] > row["open"] and previous["close"] < previous["open"]:
        labels.append("FGD")

    if row["close"] < row["open"] and previous["close"] > previous["open"]:
        labels.append("FRD")

    if index >= 2:
        two_back = daily.loc[index - 2]
        if row["close"] > previous["close"] > two_back["close"]:
            labels.append("3DL")
        if row["close"] < previous["close"] < two_back["close"]:
            labels.append("3DS")

    return labels


def _label_kind(label: str) -> str:
    return label.lower().replace(" ", "_")


def _level(key: str, label: str, price: Any, color: str, start_time: Any) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "price": float(price),
        "color": color,
        "style": "solid",
        "start_time": pd.Timestamp(start_time).isoformat(),
    }


def _previous_week_slice(daily: pd.DataFrame, chart_end: pd.Timestamp) -> pd.DataFrame:
    week_start = _week_start(chart_end)
    previous_week_start = week_start - timedelta(days=7)
    return daily[
        (daily["candle_time"] >= previous_week_start)
        & (daily["candle_time"] < week_start)
    ]


def _latest_friday(daily: pd.DataFrame, chart_end: pd.Timestamp) -> pd.Series | None:
    friday_rows = daily[
        (daily["candle_time"] <= chart_end)
        & (daily["candle_time"].dt.weekday == 4)
    ]
    if friday_rows.empty:
        return None
    return friday_rows.iloc[-1]


def _current_week_monday(daily: pd.DataFrame, chart_end: pd.Timestamp) -> pd.Series | None:
    week_start = _week_start(chart_end)
    monday_rows = daily[
        (daily["candle_time"] >= week_start)
        & (daily["candle_time"] < week_start + timedelta(days=1))
    ]
    if monday_rows.empty:
        return None
    return monday_rows.iloc[0]


def _week_start(value: pd.Timestamp) -> datetime:
    as_datetime = value.to_pydatetime()
    start = as_datetime - timedelta(days=as_datetime.weekday())
    return datetime(start.year, start.month, start.day, tzinfo=UTC)

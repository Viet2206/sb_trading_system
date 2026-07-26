from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any, Callable

import pandas as pd

from sb_system.market_data import fetch_candles


CandleFetcher = Callable[..., pd.DataFrame]


HORIZONTAL_LEVEL_COLOR = "#38bdf8"
DAY_RANGE_PIPE_COLOR = "#64748b"
DAY_CLOSE_SEGMENT_COLOR = "#16a34a"
SESSION_FILL_COLOR = "#94a3b8"
CIB_BULLISH_COLOR = "#16a34a"
CIB_BEARISH_COLOR = "#ef4444"

SESSION_WINDOWS = [
    ("asia", "Asia", time(3, 0), time(6, 0), SESSION_FILL_COLOR),
    ("london", "London", time(9, 0), time(12, 0), SESSION_FILL_COLOR),
    ("new_york", "New York", time(15, 0), time(18, 0), SESSION_FILL_COLOR),
]


def build_sb_overlays(
    source: Any,
    *,
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = None,
    fetcher: CandleFetcher = fetch_candles,
) -> dict[str, Any]:
    chart_candles = fetcher(
        source,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
    )
    daily_candles = fetcher(source, symbol=symbol, timeframe="D1", limit=420)

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
            "cib_markers": [],
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
    cib_markers = _build_cib_markers(chart, daily) if apply_intraday_template else []
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
        "cib_markers": cib_markers,
        "day_labels": day_labels,
        "setup_labels": setup_labels,
        "notes": [
            "FGD, FRD, 3DL, and 3DS are deterministic daily-candle labels and should be refined against manually tagged SB examples.",
            "Session windows use chart/data time: Asia 03:00-06:00, London 09:00-12:00, New York 15:00-18:00.",
            "Intraday day-period and session templates are hidden on H4 and D1 charts.",
            "Horizontal context levels are solid right-extending rays from their relevant start time.",
            "Monthly context includes previous-month high/low and current-month first trading-day high/low.",
            "Intraday previous-day high/low levels are drawn as connected range pipes.",
            "A compact candle-body marker at each day boundary identifies a previous-day Closing Inside Breakout.",
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
                    _level("previous_day_high", "PDH", previous_day["high"], HORIZONTAL_LEVEL_COLOR, current_day_start),
                    _level("previous_day_low", "PDL", previous_day["low"], HORIZONTAL_LEVEL_COLOR, current_day_start),
                ]
            )
        if include_previous_day_close:
            levels.append(_level("previous_day_close", "PDC", previous_day["close"], HORIZONTAL_LEVEL_COLOR, current_day_start))

    month_start = _month_start(chart_end)
    previous_month = _previous_month_slice(daily, chart_end)
    if not previous_month.empty:
        levels.extend(
            [
                _level(
                    "previous_month_high",
                    "PMH",
                    previous_month["high"].max(),
                    HORIZONTAL_LEVEL_COLOR,
                    month_start,
                ),
                _level(
                    "previous_month_low",
                    "PML",
                    previous_month["low"].min(),
                    HORIZONTAL_LEVEL_COLOR,
                    month_start,
                ),
            ]
        )

    first_month_day = _current_month_first_day(daily, chart_end)
    if first_month_day is not None:
        levels.extend(
            [
                _level(
                    "current_month_first_day_high",
                    "1st Day High",
                    first_month_day["high"],
                    HORIZONTAL_LEVEL_COLOR,
                    first_month_day["candle_time"],
                ),
                _level(
                    "current_month_first_day_low",
                    "1st Day Low",
                    first_month_day["low"],
                    HORIZONTAL_LEVEL_COLOR,
                    first_month_day["candle_time"],
                ),
            ]
        )

    week_start = _week_start(chart_end)
    previous_week = _previous_week_slice(daily, chart_end)
    if not previous_week.empty:
        levels.extend(
            [
                _level("previous_week_high", "PWH", previous_week["high"].max(), HORIZONTAL_LEVEL_COLOR, week_start),
                _level("previous_week_low", "PWL", previous_week["low"].min(), HORIZONTAL_LEVEL_COLOR, week_start),
            ]
        )

    friday = _latest_friday(daily, chart_end)
    if friday is not None:
        levels.append(_level("friday_close", "Fri Close", friday["close"], HORIZONTAL_LEVEL_COLOR, friday["candle_time"]))

    monday = _current_week_monday(daily, chart_end)
    if monday is not None:
        levels.extend(
            [
                _level("current_monday_high", "Mon High", monday["high"], HORIZONTAL_LEVEL_COLOR, monday["candle_time"]),
                _level("current_monday_low", "Mon Low", monday["low"], HORIZONTAL_LEVEL_COLOR, monday["candle_time"]),
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
                "color": DAY_RANGE_PIPE_COLOR,
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
                "color": DAY_CLOSE_SEGMENT_COLOR,
                "style": "solid",
            }
        )

    return segments


def _build_cib_markers(chart: pd.DataFrame, daily: pd.DataFrame) -> list[dict[str, Any]]:
    if daily.empty:
        return []

    markers: list[dict[str, Any]] = []
    for day, day_slice in chart.groupby(chart["candle_time"].dt.date):
        previous_days = daily[daily["candle_time"].dt.date < day]
        if len(previous_days) < 2:
            continue

        previous_index = int(previous_days.index[-1])
        if not _is_closing_inside_breakout(daily, previous_index):
            continue

        previous_day = daily.loc[previous_index]
        direction = _candle_direction(previous_day)
        if direction is None:
            continue

        boundary_time = day_slice.iloc[0]["candle_time"].to_pydatetime()
        markers.append(
            {
                "id": f"cib-{day.isoformat()}",
                "time": boundary_time.isoformat(),
                "open": float(previous_day["open"]),
                "close": float(previous_day["close"]),
                "direction": direction,
                "color": (
                    CIB_BULLISH_COLOR
                    if direction == "green"
                    else CIB_BEARISH_COLOR
                ),
            }
        )

    return markers


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
    direction = _candle_direction(row)

    if row["high"] < previous["high"] and row["low"] > previous["low"]:
        labels.append("Inside Day")

    if direction == "green" and _previous_direction_count(daily, index, "red") >= 2:
        labels.append("FGD")

    if direction == "red" and _previous_direction_count(daily, index, "green") >= 2:
        labels.append("FRD")

    if index >= 2 and direction is not None:
        previous_direction = _candle_direction(previous)
        two_back_direction = _candle_direction(daily.loc[index - 2])
        three_back_direction = _candle_direction(daily.loc[index - 3]) if index >= 3 else None
        is_third_day = (
            previous_direction == direction
            and two_back_direction == direction
            and three_back_direction != direction
        )
        if is_third_day and direction == "green":
            labels.append("3DL")
        if is_third_day and direction == "red":
            labels.append("3DS")

    return labels


def _candle_direction(row: pd.Series) -> str | None:
    if row["close"] > row["open"]:
        return "green"
    if row["close"] < row["open"]:
        return "red"
    return None


def _is_closing_inside_breakout(daily: pd.DataFrame, index: int) -> bool:
    if index <= 0:
        return False

    row = daily.loc[index]
    previous = daily.loc[index - 1]
    closes_inside = (
        float(previous["low"])
        < float(row["close"])
        < float(previous["high"])
    )
    breaks_range = (
        float(row["high"]) > float(previous["high"])
        or float(row["low"]) < float(previous["low"])
    )
    return closes_inside and breaks_range


def _previous_direction_count(daily: pd.DataFrame, index: int, direction: str) -> int:
    count = 0
    current = index - 1
    while current >= 0 and _candle_direction(daily.loc[current]) == direction:
        count += 1
        current -= 1
    return count


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


def _previous_month_slice(daily: pd.DataFrame, chart_end: pd.Timestamp) -> pd.DataFrame:
    current_month_start = _month_start(chart_end)
    if current_month_start.month == 1:
        previous_month_start = datetime(
            current_month_start.year - 1,
            12,
            1,
            tzinfo=UTC,
        )
    else:
        previous_month_start = datetime(
            current_month_start.year,
            current_month_start.month - 1,
            1,
            tzinfo=UTC,
        )
    return daily[
        (daily["candle_time"] >= previous_month_start)
        & (daily["candle_time"] < current_month_start)
    ]


def _current_month_first_day(
    daily: pd.DataFrame,
    chart_end: pd.Timestamp,
) -> pd.Series | None:
    month_start = _month_start(chart_end)
    month_rows = daily[
        (daily["candle_time"] >= month_start)
        & (daily["candle_time"] <= chart_end)
    ]
    if month_rows.empty:
        return None
    return month_rows.iloc[0]


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


def _month_start(value: pd.Timestamp) -> datetime:
    return datetime(value.year, value.month, 1, tzinfo=UTC)

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from sb_system.context import _classify_day, _candle_direction, _week_start
from sb_system.market_data import PROJECT_ROOT, fetch_candles


CandleFetcher = Callable[..., pd.DataFrame]
CHECKLIST_STATE_PATH = PROJECT_ROOT / "data" / "runtime" / "daily_checklist.json"


SESSION_PLAN = [
    {
        "id": "asia",
        "label": "Asia",
        "time": "03:00-06:00",
        "focus": "JPY crosses, AUD/NZD, XAUUSD; wait for HOS/LOS or false break around daily extremes.",
    },
    {
        "id": "london",
        "label": "London",
        "time": "09:00-12:00",
        "focus": "Major FX and XAUUSD; best window for HOD/LOD, backside continuation, and day-three reversals.",
    },
    {
        "id": "new_york",
        "label": "New York",
        "time": "15:00-18:00",
        "focus": "Major FX, XAUUSD, NAS100, SP500; trade after major news only.",
    },
]


DEFAULT_MANUAL_CHECKS = [
    "major_news_clear",
    "correct_session_window",
    "m15_setup_visible",
    "m5_entry_trigger_visible",
    "ema20_close_confirmation",
    "stop_within_limit",
    "target_preset",
    "moves_fast_after_entry",
]


@dataclass(frozen=True)
class ChecklistState:
    date: str
    symbol: str | None
    checks: dict[str, bool]
    journal: dict[str, Any]


def build_daily_checklist(
    source: Any,
    *,
    symbols: Iterable[str],
    target_date: date | None = None,
    fetcher: CandleFetcher = fetch_candles,
) -> dict[str, Any]:
    rows = []
    daily_by_symbol = {}
    for symbol in sorted(set(symbols)):
        daily = fetcher(source, symbol=symbol, timeframe="D1", limit=420)
        if not daily.empty:
            daily_by_symbol[symbol] = _prepare_daily(daily)
        row = _build_symbol_row(symbol, daily, target_date)
        if row is not None:
            rows.append(row)

    rows = sorted(rows, key=lambda item: (-item["quality_score"], item["symbol"]))
    selected_date = _selected_date(rows, target_date)
    weekly_matrix = _build_weekly_matrix(daily_by_symbol, selected_date)

    return {
        "date": selected_date.isoformat() if selected_date else None,
        "generated_at": datetime.now(UTC).isoformat(),
        "rows": rows,
        "weekly_matrix": weekly_matrix,
        "sessions": SESSION_PLAN,
        "manual_checks": _manual_check_definitions(),
        "state": load_checklist_state(selected_date.isoformat() if selected_date else None),
    }


def load_checklist_state(target_date: str | None = None, path: Path = CHECKLIST_STATE_PATH) -> dict[str, Any]:
    states = _read_state_file(path)
    if target_date is None:
        return _state_payload(ChecklistState(date="", symbol=None, checks={}, journal={}))

    state = states.get(target_date)
    if not isinstance(state, dict):
        return _state_payload(_default_state(target_date))

    checks = state.get("checks") if isinstance(state.get("checks"), dict) else {}
    journal = state.get("journal") if isinstance(state.get("journal"), dict) else {}
    return _state_payload(
        ChecklistState(
            date=target_date,
            symbol=state.get("symbol") if isinstance(state.get("symbol"), str) else None,
            checks={str(key): bool(value) for key, value in checks.items()},
            journal=journal,
        )
    )


def save_checklist_state(payload: dict[str, Any], path: Path = CHECKLIST_STATE_PATH) -> dict[str, Any]:
    raw_date = payload.get("date")
    if not isinstance(raw_date, str) or not raw_date:
        raise ValueError("Daily checklist state requires a date.")

    raw_checks = payload.get("checks")
    checks = raw_checks if isinstance(raw_checks, dict) else {}
    state = ChecklistState(
        date=raw_date,
        symbol=payload.get("symbol") if isinstance(payload.get("symbol"), str) else None,
        checks={str(key): bool(value) for key, value in checks.items()},
        journal=payload.get("journal") if isinstance(payload.get("journal"), dict) else {},
    )

    states = _read_state_file(path)
    states[state.date] = _state_payload(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(states, indent=2, sort_keys=True), encoding="utf-8")
    return _state_payload(state)


def _build_symbol_row(symbol: str, daily_candles: pd.DataFrame, target_date: date | None) -> dict[str, Any] | None:
    if daily_candles.empty:
        return None

    daily = _prepare_daily(daily_candles)
    if target_date is not None:
        daily = daily[daily["candle_time"].dt.date <= target_date].reset_index(drop=True)
    if len(daily) < 2:
        return None

    index = len(daily) - 1
    current = daily.loc[index]
    previous = daily.loc[index - 1]
    direction = _candle_direction(current) or "flat"
    labels = _classify_day(daily, index)
    previous_labels = _classify_day(daily, index - 1) if index >= 1 else []
    day_count = _direction_count(daily, index, direction)
    week = _week_context(daily, current)
    location = _price_location(daily, current, previous, week)
    candidate = _candidate_direction(labels, previous_labels)
    no_trade = _no_trade_reasons(labels, previous_labels, location)
    score = _quality_score(labels, previous_labels, location, no_trade)

    return {
        "symbol": symbol,
        "last_candle_time": current["candle_time"].isoformat(),
        "day_of_week": current["candle_time"].strftime("%a"),
        "direction": direction,
        "day_count": day_count,
        "signal_days": labels,
        "previous_signal_days": previous_labels,
        "weekly_template_state": week["state"],
        "price_location": location,
        "candidate_direction": candidate,
        "quality_score": score,
        "no_trade_reasons": no_trade,
        "context": {
            "open": float(current["open"]),
            "high": float(current["high"]),
            "low": float(current["low"]),
            "close": float(current["close"]),
            "previous_day_high": float(previous["high"]),
            "previous_day_low": float(previous["low"]),
            "previous_day_close": float(previous["close"]),
            "previous_week_high": week["previous_week_high"],
            "previous_week_low": week["previous_week_low"],
            "monday_high": week["monday_high"],
            "monday_low": week["monday_low"],
            "friday_close": week["friday_close"],
            "average_daily_range": _average_daily_range(daily),
        },
        "setup_checklist": _setup_checklist(labels, previous_labels),
    }


def _prepare_daily(candles: pd.DataFrame) -> pd.DataFrame:
    prepared = candles.copy()
    prepared["candle_time"] = pd.to_datetime(prepared["candle_time"], utc=True)
    return prepared.sort_values("candle_time").reset_index(drop=True)


def _direction_count(daily: pd.DataFrame, index: int, direction: str) -> int:
    if direction not in {"green", "red"}:
        return 0
    count = 0
    current = index
    while current >= 0 and _candle_direction(daily.loc[current]) == direction:
        count += 1
        current -= 1
    return count


def _week_context(daily: pd.DataFrame, current: pd.Series) -> dict[str, Any]:
    current_time = pd.Timestamp(current["candle_time"])
    week_start = pd.Timestamp(_week_start(current_time))
    current_week = daily[
        (daily["candle_time"] >= week_start)
        & (daily["candle_time"] <= current_time)
    ]
    previous_week = daily[
        (daily["candle_time"] >= week_start - pd.Timedelta(days=7))
        & (daily["candle_time"] < week_start)
    ]
    monday_rows = current_week[current_week["candle_time"].dt.weekday == 0]
    friday_rows = daily[
        (daily["candle_time"] < week_start)
        & (daily["candle_time"].dt.weekday == 4)
    ]

    monday_high = float(monday_rows.iloc[0]["high"]) if not monday_rows.empty else None
    monday_low = float(monday_rows.iloc[0]["low"]) if not monday_rows.empty else None
    close = float(current["close"])

    if current_time.weekday() == 0:
        state = "Monday Opening Range"
    elif monday_high is not None and close > monday_high:
        state = "Range Expansion Up"
    elif monday_low is not None and close < monday_low:
        state = "Range Expansion Down"
    elif monday_high is not None and monday_low is not None:
        state = "Inside Monday Range"
    else:
        state = "Weekly Context Pending"

    return {
        "state": state,
        "previous_week_high": float(previous_week["high"].max()) if not previous_week.empty else None,
        "previous_week_low": float(previous_week["low"].min()) if not previous_week.empty else None,
        "monday_high": monday_high,
        "monday_low": monday_low,
        "friday_close": float(friday_rows.iloc[-1]["close"]) if not friday_rows.empty else None,
    }


def _price_location(
    daily: pd.DataFrame,
    current: pd.Series,
    previous: pd.Series,
    week: dict[str, Any],
) -> list[str]:
    close = float(current["close"])
    average_range = _average_daily_range(daily)
    tolerance = max(average_range * 0.2, abs(close) * 0.001)
    checks = [
        ("Near PDH", float(previous["high"])),
        ("Near PDL", float(previous["low"])),
        ("Near PDC", float(previous["close"])),
        ("Near PWH", week["previous_week_high"]),
        ("Near PWL", week["previous_week_low"]),
        ("Near Monday High", week["monday_high"]),
        ("Near Monday Low", week["monday_low"]),
        ("Near Friday Close", week["friday_close"]),
    ]

    labels = [label for label, price in checks if price is not None and abs(close - float(price)) <= tolerance]
    if not labels:
        labels.append("Middle of Range")
    return labels


def _average_daily_range(daily: pd.DataFrame) -> float:
    recent = daily.tail(20)
    if recent.empty:
        return 0.0
    return float((recent["high"] - recent["low"]).mean())


def _candidate_direction(labels: list[str], previous_labels: list[str]) -> str:
    combined = labels + previous_labels
    if "FGD" in combined:
        return "Buy"
    if "FRD" in combined:
        return "Sell"
    if "3DL" in combined:
        return "Watch Sell Reversal"
    if "3DS" in combined:
        return "Watch Buy Reversal"
    if "Inside Day" in combined:
        return "Wait for Break/False Break"
    return "Wait"


def _no_trade_reasons(labels: list[str], previous_labels: list[str], location: list[str]) -> list[str]:
    reasons = []
    if not labels and not previous_labels:
        reasons.append("No signal day")
    if location == ["Middle of Range"]:
        reasons.append("Middle of range")
    return reasons


def _quality_score(
    labels: list[str],
    previous_labels: list[str],
    location: list[str],
    no_trade_reasons: list[str],
) -> int:
    score = 20
    combined = labels + previous_labels
    if any(label in combined for label in ["FGD", "FRD"]):
        score += 35
    if any(label in combined for label in ["3DL", "3DS"]):
        score += 25
    if "Inside Day" in combined:
        score += 18
    if location != ["Middle of Range"]:
        score += 15
    score -= len(no_trade_reasons) * 10
    return min(100, max(0, score))


def _setup_checklist(labels: list[str], previous_labels: list[str]) -> list[str]:
    combined = labels + previous_labels
    if "FRD" in combined:
        return [
            "Pump day exists before signal day",
            "Signal day closes below open",
            "Consolidation box forms into close",
            "Trade day offers HOD/HOS sell setup",
        ]
    if "FGD" in combined:
        return [
            "Dump day exists before signal day",
            "Signal day closes above open",
            "Consolidation box forms into close",
            "Trade day offers LOD/LOS buy setup",
        ]
    if "Inside Day" in combined:
        return [
            "Inside-day high and low are marked",
            "Breakout traders trigger one side",
            "False break or continuation confirms",
            "Target opposite side or measured range",
        ]
    if "3DL" in combined or "3DS" in combined:
        return [
            "Day 1 breakout traders entered",
            "Day 2 breakout traders entered",
            "Day 3 traps late breakout traders",
            "Reversal confirms inside session window",
        ]
    return [
        "Signal day is visible on D1",
        "Setup is clear on M15",
        "Entry trigger is clear on M5",
        "Risk and target are predefined",
    ]


def _build_weekly_matrix(
    daily_by_symbol: dict[str, pd.DataFrame],
    selected_date: date | None,
) -> dict[str, Any]:
    if selected_date is None:
        return {"columns": [], "rows": []}

    selected_timestamp = pd.Timestamp(datetime.combine(selected_date, datetime.min.time(), tzinfo=UTC))
    week_start = pd.Timestamp(_week_start(selected_timestamp))
    previous_friday = week_start - pd.Timedelta(days=3)
    column_dates = [previous_friday] + [week_start + pd.Timedelta(days=offset) for offset in range(5)]
    columns = [
        {
            "key": "previous_friday" if index == 0 else column_time.strftime("%a").lower(),
            "label": "Fri*" if index == 0 else column_time.strftime("%a"),
            "date": column_time.date().isoformat(),
        }
        for index, column_time in enumerate(column_dates)
    ]

    rows = []
    for symbol, daily in sorted(daily_by_symbol.items()):
        daily = daily[daily["candle_time"].dt.date <= selected_date].reset_index(drop=True)
        cells = []
        for column in columns:
            cell_date = date.fromisoformat(column["date"])
            cells.append(_matrix_cell(daily, cell_date))
        rows.append(
            {
                "symbol": symbol,
                "highlight": any(cell["strength"] == "strong" for cell in cells),
                "cells": cells,
            }
        )

    return {"columns": columns, "rows": rows}


def _matrix_cell(daily: pd.DataFrame, cell_date: date) -> dict[str, Any]:
    matches = daily[daily["candle_time"].dt.date == cell_date]
    if matches.empty:
        return {
            "date": cell_date.isoformat(),
            "text": "",
            "labels": [],
            "direction": "none",
            "tone": "empty",
            "strength": "none",
        }

    index = int(matches.index[-1])
    row = daily.loc[index]
    direction = _candle_direction(row) or "flat"
    labels = _matrix_signal_labels(daily, index)
    text = _matrix_text(labels, direction)
    tone = _matrix_tone(labels, direction)
    strength = "strong" if any(label in {"3DL", "3DS"} for label in labels) else "signal" if labels else "normal"

    return {
        "date": cell_date.isoformat(),
        "text": text,
        "labels": labels,
        "direction": direction,
        "tone": tone,
        "strength": strength,
    }


def _matrix_signal_labels(daily: pd.DataFrame, index: int) -> list[str]:
    labels = _classify_day(daily, index)
    matrix_labels = []

    if "Inside Day" in labels:
        matrix_labels.append("ID")
    for label in labels:
        if label != "Inside Day":
            matrix_labels.append(label)

    cib_label = _cib_label(daily, index)
    if cib_label and "ID" not in matrix_labels:
        matrix_labels.append(cib_label)

    return matrix_labels


def _cib_label(daily: pd.DataFrame, index: int) -> str | None:
    if index <= 0:
        return None

    if not _close_inside_previous_range(daily, index):
        return None

    previous_is_cib = _close_inside_previous_range(daily, index - 1) if index >= 2 else False
    return "2CIB" if previous_is_cib else "CIB"


def _close_inside_previous_range(daily: pd.DataFrame, index: int) -> bool:
    if index <= 0:
        return False
    row = daily.loc[index]
    previous = daily.loc[index - 1]
    return float(previous["low"]) < float(row["close"]) < float(previous["high"])


def _matrix_text(labels: list[str], direction: str) -> str:
    arrow = _direction_arrow(direction)
    if not labels:
        return arrow
    return " ".join(labels + ([arrow] if arrow else []))


def _direction_arrow(direction: str) -> str:
    if direction == "green":
        return "▲"
    if direction == "red":
        return "▼"
    return ""


def _matrix_tone(labels: list[str], direction: str) -> str:
    if "3DL" in labels or (
        direction == "green" and any(label in labels for label in ["FGD", "CIB", "2CIB"])
    ):
        return "bullish"
    if "3DS" in labels or (
        direction == "red" and any(label in labels for label in ["FRD", "CIB", "2CIB"])
    ):
        return "bearish"
    if "ID" in labels:
        return "inside"
    if direction == "green":
        return "bullish"
    if direction == "red":
        return "bearish"
    return "neutral"


def _selected_date(rows: list[dict[str, Any]], target_date: date | None) -> date | None:
    if target_date is not None:
        return target_date
    if not rows:
        return None
    return max(pd.Timestamp(row["last_candle_time"]).date() for row in rows)


def _manual_check_definitions() -> list[dict[str, str]]:
    return [
        {"id": "major_news_clear", "label": "No major red news in session"},
        {"id": "correct_session_window", "label": "Inside 3-hour session window"},
        {"id": "m15_setup_visible", "label": "M15 setup is clear"},
        {"id": "m5_entry_trigger_visible", "label": "M5 entry trigger is clear"},
        {"id": "ema20_close_confirmation", "label": "20 EMA close confirms entry"},
        {"id": "stop_within_limit", "label": "Stop is within max limit"},
        {"id": "target_preset", "label": "Take-profit is preset"},
        {"id": "moves_fast_after_entry", "label": "Trade moves fast after entry"},
    ]


def _default_state(target_date: str) -> ChecklistState:
    return ChecklistState(
        date=target_date,
        symbol=None,
        checks={key: False for key in DEFAULT_MANUAL_CHECKS},
        journal={
            "did_trade": "no",
            "setup_grade": "",
            "result": "",
            "mistake_tag": "",
            "notes": "",
        },
    )


def _state_payload(state: ChecklistState) -> dict[str, Any]:
    return {
        "date": state.date,
        "symbol": state.symbol,
        "checks": state.checks,
        "journal": state.journal,
    }


def _read_state_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}

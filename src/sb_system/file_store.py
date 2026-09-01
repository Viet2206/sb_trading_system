from __future__ import annotations

import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd


CANDLE_COLUMNS = [
    "broker_symbol",
    "timeframe",
    "candle_time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
]
SUMMARY_INDEX_NAME = ".candle-summary.json"
SUMMARY_COLUMNS = ["broker_symbol", "timeframe", "first_candle", "last_candle", "candles"]


def fetch_file_candle_summary(data_dir: Path, *, file_format: str = "csv.gz") -> pd.DataFrame:
    rows = _read_summary_index(data_dir)
    if not rows:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)

    summary = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    summary["first_candle"] = pd.to_datetime(summary["first_candle"], utc=True)
    summary["last_candle"] = pd.to_datetime(summary["last_candle"], utc=True)
    summary["candles"] = summary["candles"].astype(int)
    return summary.sort_values(["broker_symbol", "timeframe"]).reset_index(drop=True)


def rebuild_file_candle_summary(data_dir: Path, *, file_format: str = "csv.gz") -> pd.DataFrame:
    """Build the lightweight summary index once for a legacy candle directory."""
    rows: list[dict[str, Any]] = []
    for file_path in _iter_candle_files(data_dir, file_format=file_format):
        candles = _read_candles(file_path)
        if candles.empty:
            continue
        rows.extend(_summary_rows(candles))
    _write_summary_index(data_dir, rows)
    return fetch_file_candle_summary(data_dir, file_format=file_format)


def fetch_file_symbols(data_dir: Path, *, file_format: str = "csv.gz") -> pd.DataFrame:
    summary = fetch_file_candle_summary(data_dir, file_format=file_format)
    if summary.empty:
        return pd.DataFrame(
            columns=[
                "broker_symbol",
                "base_symbol",
                "description",
                "digits",
                "point",
                "trade_contract_size",
                "currency_base",
                "currency_profit",
                "currency_margin",
                "first_candle",
                "last_candle",
                "candles",
            ]
        )

    grouped = summary.groupby("broker_symbol", as_index=False).agg(
        first_candle=("first_candle", "min"),
        last_candle=("last_candle", "max"),
        candles=("candles", "sum"),
    )
    for column in [
        "base_symbol",
        "description",
        "digits",
        "point",
        "trade_contract_size",
        "currency_base",
        "currency_profit",
        "currency_margin",
    ]:
        grouped[column] = None

    return grouped[
        [
            "broker_symbol",
            "base_symbol",
            "description",
            "digits",
            "point",
            "trade_contract_size",
            "currency_base",
            "currency_profit",
            "currency_margin",
            "first_candle",
            "last_candle",
            "candles",
        ]
    ].sort_values("broker_symbol").reset_index(drop=True)


def fetch_file_candles(
    data_dir: Path,
    *,
    symbol: str,
    timeframe: str,
    file_format: str = "csv.gz",
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int | None = 500,
) -> pd.DataFrame:
    file_path = candle_file_path(data_dir, symbol=symbol, timeframe=timeframe, file_format=file_format)
    candles = _read_candles(file_path)
    if candles.empty:
        return candles

    selected = candles[
        (candles["broker_symbol"] == symbol)
        & (candles["timeframe"] == timeframe)
    ].copy()

    if start is not None:
        selected = selected[selected["candle_time"] >= _utc_timestamp(start)]
    if end is not None:
        selected = selected[selected["candle_time"] <= _utc_timestamp(end)]

    selected = selected.sort_values("candle_time")
    if limit is not None:
        selected = selected.tail(limit)

    return selected.reset_index(drop=True)


def upsert_file_candles(
    data_dir: Path,
    candles: pd.DataFrame,
    *,
    file_format: str = "csv.gz",
    retain_from: datetime | None = None,
) -> int:
    if candles.empty:
        return 0

    missing = set(CANDLE_COLUMNS).difference(candles.columns)
    if missing:
        raise ValueError(f"Missing required candle columns: {sorted(missing)}")

    rows = candles[CANDLE_COLUMNS].copy()
    rows["candle_time"] = pd.to_datetime(rows["candle_time"], utc=True)
    rows = rows.sort_values("candle_time")

    written = 0
    for (symbol, timeframe), group in rows.groupby(["broker_symbol", "timeframe"], sort=True):
        file_path = candle_file_path(data_dir, symbol=symbol, timeframe=timeframe, file_format=file_format)
        existing = _read_candles(file_path)
        merged = pd.concat([existing, group], ignore_index=True)
        merged["candle_time"] = pd.to_datetime(merged["candle_time"], utc=True)
        if retain_from is not None:
            merged = merged[merged["candle_time"] >= _utc_timestamp(retain_from)]
        merged = (
            merged.drop_duplicates(["broker_symbol", "timeframe", "candle_time"], keep="last")
            .sort_values("candle_time")
            .reset_index(drop=True)
        )
        _write_candles(file_path, merged, file_format=file_format)
        _upsert_summary_index(data_dir, _summary_rows(merged))
        written += len(group)

    return written


def latest_file_candle_time(
    data_dir: Path,
    *,
    symbol: str,
    timeframe: str,
    file_format: str = "csv.gz",
) -> pd.Timestamp | None:
    candles = fetch_file_candles(
        data_dir,
        symbol=symbol,
        timeframe=timeframe,
        file_format=file_format,
        limit=1,
    )
    if candles.empty:
        return None
    return pd.Timestamp(candles.iloc[-1]["candle_time"])


def candle_file_path(data_dir: Path, *, symbol: str, timeframe: str, file_format: str = "csv.gz") -> Path:
    extension = ".csv.gz" if file_format == "csv.gz" else f".{file_format}"
    return data_dir / _safe_name(symbol) / f"{timeframe}{extension}"


def _iter_candle_files(data_dir: Path, *, file_format: str) -> list[Path]:
    if not data_dir.exists():
        return []

    if file_format == "csv.gz":
        pattern = "*.csv.gz"
    else:
        pattern = f"*.{file_format}"

    return sorted(path for path in data_dir.rglob(pattern) if path.is_file())


def _read_candles(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        return pd.DataFrame(columns=CANDLE_COLUMNS)

    stat = file_path.stat()
    return _read_candles_cached(str(file_path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=8)
def _read_candles_cached(file_path_value: str, _mtime_ns: int, _size: int) -> pd.DataFrame:
    file_path = Path(file_path_value)

    if file_path.name.endswith(".parquet"):
        candles = pd.read_parquet(file_path)
    else:
        candles = pd.read_csv(file_path)

    if candles.empty:
        return pd.DataFrame(columns=CANDLE_COLUMNS)

    candles = candles.copy()
    candles["candle_time"] = pd.to_datetime(candles["candle_time"], utc=True)
    return candles[CANDLE_COLUMNS].sort_values("candle_time").reset_index(drop=True)


def _write_candles(file_path: Path, candles: pd.DataFrame, *, file_format: str) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = file_path.with_name(f".{file_path.name}.{uuid4().hex}.tmp")
    try:
        if file_format == "parquet":
            candles.to_parquet(temporary_path, index=False)
        elif file_format == "csv.gz":
            candles.to_csv(temporary_path, index=False, compression="gzip")
        else:
            candles.to_csv(temporary_path, index=False)
        os.replace(temporary_path, file_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _summary_rows(candles: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (broker_symbol, timeframe), group in candles.groupby(["broker_symbol", "timeframe"]):
        rows.append(
            {
                "broker_symbol": str(broker_symbol),
                "timeframe": str(timeframe),
                "first_candle": pd.Timestamp(group["candle_time"].min()).isoformat(),
                "last_candle": pd.Timestamp(group["candle_time"].max()).isoformat(),
                "candles": int(len(group)),
            }
        )
    return rows


def _summary_index_path(data_dir: Path) -> Path:
    return data_dir / SUMMARY_INDEX_NAME


def _read_summary_index(data_dir: Path) -> list[dict[str, Any]]:
    index_path = _summary_index_path(data_dir)
    if not index_path.exists():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("rows", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _upsert_summary_index(data_dir: Path, updates: list[dict[str, Any]]) -> None:
    indexed = {
        (row.get("broker_symbol"), row.get("timeframe")): row
        for row in _read_summary_index(data_dir)
    }
    for row in updates:
        indexed[(row["broker_symbol"], row["timeframe"])] = row
    _write_summary_index(data_dir, list(indexed.values()))


def _write_summary_index(data_dir: Path, rows: list[dict[str, Any]]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    index_path = _summary_index_path(data_dir)
    temporary_path = index_path.with_name(f".{index_path.name}.{uuid4().hex}.tmp")
    payload = {
        "version": 1,
        "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "rows": sorted(rows, key=lambda row: (row["broker_symbol"], row["timeframe"])),
    }
    try:
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary_path, index_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value)


def _utc_timestamp(value: datetime) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")

from __future__ import annotations

from datetime import UTC, datetime


CHART_WINDOW_MONTHS = 3
MAX_CHART_CANDLES = 50_000


def chart_window_start(reference: datetime | None = None, *, months: int = CHART_WINDOW_MONTHS) -> datetime:
    """Return the first day of the month `months` calendar months before reference."""
    current = reference or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    else:
        current = current.astimezone(UTC)

    month_index = current.year * 12 + current.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    return datetime(year, zero_based_month + 1, 1, tzinfo=UTC)

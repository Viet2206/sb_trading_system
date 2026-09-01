from __future__ import annotations

import unittest
from datetime import UTC, datetime

from sb_system.chart_window import chart_window_start


class ChartWindowTests(unittest.TestCase):
    def test_three_month_window_starts_on_first_day_of_month(self) -> None:
        reference = datetime(2026, 9, 10, 14, 30, tzinfo=UTC)
        self.assertEqual(
            chart_window_start(reference),
            datetime(2026, 6, 1, tzinfo=UTC),
        )

    def test_window_handles_year_boundary(self) -> None:
        reference = datetime(2026, 2, 15, tzinfo=UTC)
        self.assertEqual(
            chart_window_start(reference),
            datetime(2025, 11, 1, tzinfo=UTC),
        )


if __name__ == "__main__":
    unittest.main()

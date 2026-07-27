from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sb_system.example_matching import (
    ExampleFeedbackStore,
    HistoricalExampleMatcher,
    build_chart_fingerprint,
)


class _FakeResearchLibrary:
    def search(self, query: str, *, limit: int = 12, **_kwargs):
        self.query = query
        self.limit = limit
        return {
            "query": query,
            "count": 3,
            "results": [
                {
                    "citation": "S1",
                    "score": 0.52,
                    "document_id": "fgd-examples",
                    "document_title": "First Green Day Trade Setup Examples",
                    "category": "Chart Template Notes",
                    "page": 4,
                    "setup_types": ["first-green-day"],
                    "excerpt": "First Green Day buy setup at the low of day.",
                    "visual_only": False,
                },
                {
                    "citation": "S2",
                    "score": 0.48,
                    "document_id": "fgd-examples",
                    "document_title": "First Green Day Trade Setup Examples",
                    "category": "Chart Template Notes",
                    "page": 4,
                    "setup_types": ["first-green-day"],
                    "excerpt": "A duplicate passage from the same source page.",
                    "visual_only": False,
                },
                {
                    "citation": "S3",
                    "score": 0.51,
                    "document_id": "frd-examples",
                    "document_title": "First Red Day Trade Setup Examples",
                    "category": "Chart Template Notes",
                    "page": 2,
                    "setup_types": ["first-red-day"],
                    "excerpt": "First Red Day sell setup near the high of day.",
                    "visual_only": False,
                },
            ],
        }


MARKET_CONTEXT = {
    "symbol": "XAUUSD.pc",
    "last_candle_time": "2026-07-17T00:00:00+00:00",
    "direction": "green",
    "day_count": 1,
    "signal_days": [],
    "previous_signal_days": ["FGD"],
    "weekly_template_state": "Range Expansion Down",
    "price_location": ["Near PWL"],
    "candidate_direction": "Watch Buy Reversal",
}


class HistoricalExampleMatcherTests(unittest.TestCase):
    def test_fingerprint_is_stable_and_contains_deterministic_context(self) -> None:
        first = build_chart_fingerprint(MARKET_CONTEXT, "M15")
        second = build_chart_fingerprint(dict(MARKET_CONTEXT), "M15")

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.setup_types, ["first-green-day"])
        self.assertEqual(first.current_signal_labels, [])
        self.assertEqual(first.previous_signal_labels, ["FGD"])
        self.assertIn("First Green Day", first.query)
        self.assertIn("previous day", first.query)
        self.assertIn("Range Expansion Down", first.query)
        self.assertEqual(first.day_count, 1)

    def test_matcher_deduplicates_pages_and_ranks_setup_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExampleFeedbackStore(Path(directory) / "feedback.json")
            matcher = HistoricalExampleMatcher(_FakeResearchLibrary(), store)

            result = matcher.match(
                market_context=MARKET_CONTEXT,
                timeframe="M15",
                limit=8,
            )

        self.assertEqual(result["method"], "context-v1")
        self.assertFalse(result["calibrated"])
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["matches"][0]["document_id"], "fgd-examples")
        self.assertGreater(
            result["matches"][0]["match_score"],
            result["matches"][1]["match_score"],
        )
        self.assertIn(
            "Setup: First Green Day",
            result["matches"][0]["basis"],
        )

    def test_feedback_is_persisted_for_the_exact_chart_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ExampleFeedbackStore(Path(directory) / "feedback.json")
            matcher = HistoricalExampleMatcher(_FakeResearchLibrary(), store)
            first = matcher.match(
                market_context=MARKET_CONTEXT,
                timeframe="M15",
            )
            fingerprint_id = first["fingerprint"]["id"]

            saved = matcher.save_feedback(
                {
                    "fingerprint_id": fingerprint_id,
                    "document_id": "fgd-examples",
                    "page": 4,
                    "verdict": "relevant",
                    "symbol": "XAUUSD.pc",
                    "timeframe": "M15",
                }
            )
            second = matcher.match(
                market_context=MARKET_CONTEXT,
                timeframe="M15",
            )

            self.assertEqual(saved["verdict"], "relevant")
            self.assertEqual(
                second["matches"][0]["review_verdict"],
                "relevant",
            )

    def test_feedback_rejects_unknown_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            matcher = HistoricalExampleMatcher(
                _FakeResearchLibrary(),
                ExampleFeedbackStore(Path(directory) / "feedback.json"),
            )
            with self.assertRaisesRegex(ValueError, "relevant"):
                matcher.save_feedback(
                    {
                        "fingerprint_id": "fingerprint",
                        "document_id": "document",
                        "page": 1,
                        "verdict": "perfect",
                    }
                )


if __name__ == "__main__":
    unittest.main()

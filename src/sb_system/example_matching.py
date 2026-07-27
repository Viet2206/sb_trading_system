from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sb_system.market_data import PROJECT_ROOT
from sb_system.research import ResearchLibrary


DEFAULT_FEEDBACK_PATH = (
    PROJECT_ROOT / "data" / "research" / "historical_example_feedback.json"
)

SETUP_LABELS = {
    "FGD": "first-green-day",
    "FRD": "first-red-day",
    "Inside Day": "inside-day",
    "3DL": "three-day-long",
    "3DS": "three-day-short",
    "CIB": "closing-inside-breakout",
    "2CIB": "closing-inside-breakout",
}

SETUP_NAMES = {
    "first-green-day": "First Green Day",
    "first-red-day": "First Red Day",
    "inside-day": "Inside Day",
    "three-day-long": "Three Day Long",
    "three-day-short": "Three Day Short",
    "closing-inside-breakout": "Closing Inside Breakout",
}

LONG_TERMS = {"buy", "long", "bull", "bullish", "green day", "low of day", "lod"}
SHORT_TERMS = {"sell", "short", "bear", "bearish", "red day", "high of day", "hod"}
VALID_VERDICTS = {"relevant", "not_relevant", "unsure"}


@dataclass(frozen=True)
class ChartFingerprint:
    id: str
    symbol: str
    timeframe: str
    last_candle_time: str
    setup_types: list[str]
    signal_labels: list[str]
    current_signal_labels: list[str]
    previous_signal_labels: list[str]
    candidate_direction: str
    weekly_state: str
    price_location: list[str]
    daily_direction: str
    day_count: int
    query: str


class ExampleFeedbackStore:
    def __init__(self, path: Path | None = None) -> None:
        configured = os.getenv("SB_EXAMPLE_FEEDBACK_PATH", "").strip()
        self.path = path or (
            Path(configured).expanduser()
            if configured
            else DEFAULT_FEEDBACK_PATH
        )
        if not self.path.is_absolute():
            self.path = PROJECT_ROOT / self.path

    def verdict(
        self, fingerprint_id: str, document_id: str, page: int
    ) -> str | None:
        key = _feedback_key(fingerprint_id, document_id, page)
        record = self._read().get(key)
        return str(record["verdict"]) if isinstance(record, dict) else None

    def save(
        self,
        *,
        fingerprint_id: str,
        document_id: str,
        page: int,
        verdict: str,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> dict[str, Any]:
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                "Historical example verdict must be relevant, not_relevant, or unsure."
            )
        if not fingerprint_id or not document_id or page < 1:
            raise ValueError(
                "fingerprint_id, document_id, and a positive page are required."
            )

        records = self._read()
        key = _feedback_key(fingerprint_id, document_id, page)
        record = {
            "fingerprint_id": fingerprint_id,
            "document_id": document_id,
            "page": page,
            "verdict": verdict,
            "symbol": symbol,
            "timeframe": timeframe,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }
        records[key] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(records, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return record

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
        return payload if isinstance(payload, dict) else {}


class HistoricalExampleMatcher:
    def __init__(
        self,
        library: ResearchLibrary,
        feedback_store: ExampleFeedbackStore | None = None,
    ) -> None:
        self.library = library
        self.feedback_store = feedback_store or ExampleFeedbackStore()

    def match(
        self,
        *,
        market_context: dict[str, Any],
        timeframe: str,
        limit: int = 8,
    ) -> dict[str, Any]:
        fingerprint = build_chart_fingerprint(market_context, timeframe)
        search_limit = min(50, max(18, limit * 6))
        search = self.library.search(fingerprint.query, limit=search_limit)

        pages: dict[tuple[str, int], dict[str, Any]] = {}
        for result in search["results"]:
            key = (result["document_id"], int(result["page"]))
            current = pages.get(key)
            if current is None or float(result["score"]) > float(current["score"]):
                pages[key] = result

        matches = [
            self._score_match(fingerprint, result)
            for result in pages.values()
        ]
        matches.sort(
            key=lambda item: (
                -int(item["is_historical_example"]),
                -item["match_score"],
                item["document_title"],
                item["page"],
            )
        )
        selected = _select_diverse_matches(matches, limit)
        for index, match in enumerate(selected, start=1):
            match["rank"] = index

        return {
            "method": "context-v1",
            "calibrated": False,
            "score_meaning": (
                "Context and source relevance, not win probability or visual identity."
            ),
            "fingerprint": asdict(fingerprint),
            "count": len(selected),
            "matches": selected,
        }

    def save_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        page = payload.get("page")
        if not isinstance(page, int):
            raise ValueError("Historical example feedback requires an integer page.")
        return self.feedback_store.save(
            fingerprint_id=str(payload.get("fingerprint_id", "")).strip(),
            document_id=str(payload.get("document_id", "")).strip(),
            page=page,
            verdict=str(payload.get("verdict", "")).strip(),
            symbol=_optional_text(payload.get("symbol")),
            timeframe=_optional_text(payload.get("timeframe")),
        )

    def _score_match(
        self,
        fingerprint: ChartFingerprint,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        source_setups = set(result["setup_types"])
        fingerprint_setups = set(fingerprint.setup_types)
        setup_score = (
            0.5
            if not fingerprint_setups
            else (1.0 if fingerprint_setups & source_setups else 0.0)
        )
        retrieval_score = min(1.0, float(result["score"]) / 0.58)
        direction_score, source_direction = _direction_score(
            fingerprint.candidate_direction,
            " ".join(
                [
                    result["document_title"],
                    result["excerpt"],
                    " ".join(result["setup_types"]),
                ]
            ),
        )
        is_historical_example = bool(
            result["visual_only"]
            or "example" in result["document_title"].lower()
        )
        source_quality = (
            1.0
            if is_historical_example
            else 0.75
            if "chart" in result["document_title"].lower()
            else 0.55
        )
        match_score = round(
            100
            * (
                retrieval_score * 0.45
                + setup_score * 0.30
                + direction_score * 0.10
                + source_quality * 0.15
            )
        )
        basis = _match_basis(
            fingerprint,
            source_setups,
            source_direction,
            retrieval_score,
        )
        verdict = self.feedback_store.verdict(
            fingerprint.id,
            result["document_id"],
            int(result["page"]),
        )
        return {
            **result,
            "match_score": match_score,
            "match_band": _match_band(match_score),
            "components": {
                "research_relevance": round(retrieval_score, 3),
                "setup_alignment": round(setup_score, 3),
                "direction_alignment": round(direction_score, 3),
                "source_quality": round(source_quality, 3),
            },
            "basis": basis,
            "source_direction": source_direction,
            "is_historical_example": is_historical_example,
            "review_verdict": verdict,
        }


def build_chart_fingerprint(
    market_context: dict[str, Any], timeframe: str
) -> ChartFingerprint:
    symbol = str(market_context.get("symbol", "")).strip()
    last_candle_time = str(market_context.get("last_candle_time", "")).strip()
    current_signal_labels = _unique_strings(market_context.get("signal_days", []))
    previous_signal_labels = _unique_strings(
        market_context.get("previous_signal_days", [])
    )
    signal_labels = _unique_strings(
        [*current_signal_labels, *previous_signal_labels]
    )
    setup_types = _unique_strings(
        SETUP_LABELS[label] for label in signal_labels if label in SETUP_LABELS
    )
    direction = str(
        market_context.get("candidate_direction", "Watch")
    ).strip() or "Watch"
    weekly_state = str(
        market_context.get("weekly_template_state", "Weekly Context Pending")
    ).strip()
    price_location = _unique_strings(market_context.get("price_location", []))
    daily_direction = str(market_context.get("direction", "flat")).strip()
    raw_day_count = market_context.get("day_count", 0)
    day_count = int(raw_day_count) if isinstance(raw_day_count, (int, float)) else 0

    query_parts = [
        "historical Stacey Burke chart examples",
        *[
            f"current day {SETUP_NAMES.get(SETUP_LABELS[item], item)}"
            for item in current_signal_labels
            if item in SETUP_LABELS
        ],
        *[
            f"trade day after previous day {SETUP_NAMES.get(SETUP_LABELS[item], item)}"
            for item in previous_signal_labels
            if item in SETUP_LABELS
        ],
        direction,
        weekly_state,
        *price_location,
        f"{daily_direction} day",
        f"day {day_count}" if day_count else "",
        "session structure false break reversal continuation invalidation",
    ]
    query = " ".join(part for part in query_parts if part).strip()
    identity = {
        "symbol": symbol,
        "timeframe": timeframe,
        "last_candle_time": last_candle_time,
        "setup_types": setup_types,
        "current_signal_labels": current_signal_labels,
        "previous_signal_labels": previous_signal_labels,
        "direction": direction,
        "weekly_state": weekly_state,
        "price_location": price_location,
        "daily_direction": daily_direction,
        "day_count": day_count,
    }
    fingerprint_id = hashlib.sha1(
        json.dumps(identity, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    return ChartFingerprint(
        id=fingerprint_id,
        symbol=symbol,
        timeframe=timeframe,
        last_candle_time=last_candle_time,
        setup_types=setup_types,
        signal_labels=signal_labels,
        current_signal_labels=current_signal_labels,
        previous_signal_labels=previous_signal_labels,
        candidate_direction=direction,
        weekly_state=weekly_state,
        price_location=price_location,
        daily_direction=daily_direction,
        day_count=day_count,
        query=query,
    )


def _direction_score(candidate_direction: str, source_text: str) -> tuple[float, str]:
    candidate = candidate_direction.lower()
    expected = (
        "long"
        if any(term in candidate for term in ("buy", "long"))
        else "short"
        if any(term in candidate for term in ("sell", "short"))
        else "neutral"
    )
    source = source_text.lower()
    long_hits = sum(term in source for term in LONG_TERMS)
    short_hits = sum(term in source for term in SHORT_TERMS)
    source_direction = (
        "long"
        if long_hits > short_hits
        else "short"
        if short_hits > long_hits
        else "unknown"
    )
    if expected == "neutral" or source_direction == "unknown":
        return 0.5, source_direction
    return (1.0 if expected == source_direction else 0.0), source_direction


def _match_basis(
    fingerprint: ChartFingerprint,
    source_setups: set[str],
    source_direction: str,
    retrieval_score: float,
) -> list[str]:
    basis = []
    matching_setups = [
        SETUP_NAMES.get(item, item.replace("-", " "))
        for item in fingerprint.setup_types
        if item in source_setups
    ]
    if matching_setups:
        basis.append(f"Setup: {', '.join(matching_setups)}")
    if fingerprint.weekly_state:
        basis.append(f"Week: {fingerprint.weekly_state}")
    if fingerprint.price_location:
        basis.append(f"Location: {', '.join(fingerprint.price_location[:2])}")
    if source_direction != "unknown":
        basis.append(f"Source bias: {source_direction.title()}")
    if retrieval_score >= 0.7:
        basis.append("Strong source-text alignment")
    elif retrieval_score >= 0.45:
        basis.append("Moderate source-text alignment")
    return basis[:4] or ["Exploratory source match"]


def _match_band(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "moderate"
    return "exploratory"


def _select_diverse_matches(
    matches: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    historical = [match for match in matches if match["is_historical_example"]]
    pool = historical if len(historical) >= limit else matches
    groups: dict[str, list[dict[str, Any]]] = {}
    for match in pool:
        groups.setdefault(match["document_id"], []).append(match)

    selected: list[dict[str, Any]] = []
    while len(selected) < limit:
        added = False
        for group in groups.values():
            if group and len(selected) < limit:
                selected.append(group.pop(0))
                added = True
        if not added:
            break
    return selected


def _feedback_key(fingerprint_id: str, document_id: str, page: int) -> str:
    return f"{fingerprint_id}:{document_id}:{page}"


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _unique_strings(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        values = list(values) if values is not None else []
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

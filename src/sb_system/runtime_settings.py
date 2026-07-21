from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sb_system.market_data import PROJECT_ROOT


RUNTIME_SETTINGS_PATH = PROJECT_ROOT / "data" / "runtime" / "settings.json"


@dataclass(frozen=True)
class RuntimeSettings:
    update_interval_minutes: int = 5


def load_runtime_settings(path: Path = RUNTIME_SETTINGS_PATH) -> RuntimeSettings:
    default_interval = _sanitize_interval(os.getenv("SB_UPDATE_INTERVAL_MINUTES"), default=5)
    defaults = RuntimeSettings(update_interval_minutes=default_interval)

    if not path.exists():
        return defaults

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defaults

    return RuntimeSettings(
        update_interval_minutes=_sanitize_interval(
            payload.get("update_interval_minutes"),
            default=defaults.update_interval_minutes,
        )
    )


def save_runtime_settings(settings: RuntimeSettings, path: Path = RUNTIME_SETTINGS_PATH) -> RuntimeSettings:
    sanitized = RuntimeSettings(
        update_interval_minutes=_sanitize_interval(settings.update_interval_minutes, default=5)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(sanitized), indent=2), encoding="utf-8")
    return sanitized


def runtime_settings_from_payload(payload: dict[str, Any]) -> RuntimeSettings:
    return RuntimeSettings(
        update_interval_minutes=_sanitize_interval(payload.get("update_interval_minutes"), default=5)
    )


def _sanitize_interval(value: Any, *, default: int) -> int:
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return default
    return min(60, max(1, interval))

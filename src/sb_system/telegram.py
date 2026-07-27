from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


JsonPoster = Callable[[str, dict, float], dict]
DEFAULT_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
DEFAULT_TEST_MESSAGE = (
    "SB Trading System\n"
    "Telegram notifications are configured. No trading signals are enabled yet."
)


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str
    api_base_url: str = DEFAULT_TELEGRAM_API_BASE_URL
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> TelegramConfig:
        return cls(
            enabled=_env_bool("SB_TELEGRAM_ENABLED", default=False),
            bot_token=os.getenv("SB_TELEGRAM_BOT_TOKEN", "").strip(),
            chat_id=os.getenv("SB_TELEGRAM_CHAT_ID", "").strip(),
            api_base_url=(
                os.getenv(
                    "SB_TELEGRAM_API_BASE_URL",
                    DEFAULT_TELEGRAM_API_BASE_URL,
                ).strip()
                or DEFAULT_TELEGRAM_API_BASE_URL
            ).rstrip("/"),
            timeout_seconds=_env_timeout("SB_TELEGRAM_TIMEOUT_SECONDS", default=10.0),
        )


class TelegramNotifier:
    def __init__(
        self,
        config: TelegramConfig | None = None,
        *,
        poster: JsonPoster | None = None,
    ) -> None:
        self.config = config or TelegramConfig.from_env()
        self._poster = poster or _post_json

    def status(self) -> dict:
        token_configured = bool(self.config.bot_token)
        chat_id_configured = bool(self.config.chat_id)
        configured = token_configured and chat_id_configured
        return {
            "enabled": self.config.enabled,
            "configured": configured,
            "ready": self.config.enabled and configured,
            "token_configured": token_configured,
            "chat_id_configured": chat_id_configured,
        }

    def send_test(self) -> dict:
        result = self.send_message(DEFAULT_TEST_MESSAGE)
        return {
            **self.status(),
            "sent": True,
            "message_id": result.get("message_id"),
        }

    def send_message(self, text: str) -> dict:
        if not self.config.bot_token:
            raise ValueError("SB_TELEGRAM_BOT_TOKEN is not configured.")
        if not self.config.chat_id:
            raise ValueError("SB_TELEGRAM_CHAT_ID is not configured.")
        message = text.strip()
        if not message:
            raise ValueError("Telegram message cannot be empty.")

        response = self._poster(
            f"{self.config.api_base_url}/bot{self.config.bot_token}/sendMessage",
            {
                "chat_id": self.config.chat_id,
                "text": message,
                "disable_web_page_preview": True,
            },
            self.config.timeout_seconds,
        )
        if not response.get("ok"):
            description = str(response.get("description", "Unknown Telegram API error"))
            raise RuntimeError(f"Telegram rejected the message: {description}")

        result = response.get("result")
        return result if isinstance(result, dict) else {}


def _post_json(url: str, payload: dict, timeout_seconds: float) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        description = _telegram_error_description(exc)
        raise RuntimeError(
            f"Telegram API returned HTTP {exc.code}: {description}"
        ) from exc
    except URLError as exc:
        reason = str(exc.reason) if exc.reason else "connection failed"
        raise RuntimeError(f"Telegram API is unavailable: {reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Telegram API request timed out.") from exc

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Telegram API returned an invalid response.") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Telegram API returned an invalid response.")
    return result


def _telegram_error_description(exc: HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8")
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "request rejected"
    if isinstance(payload, dict):
        return str(payload.get("description", "request rejected"))
    return "request rejected"


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")


def _env_timeout(name: str, *, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if value <= 0 or value > 60:
        raise ValueError(f"{name} must be greater than 0 and no more than 60.")
    return value

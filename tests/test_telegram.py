from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from sb_system.api import app, get_telegram_notifier
from sb_system.telegram import TelegramConfig, TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def test_status_never_exposes_token_or_chat_id(self) -> None:
        notifier = TelegramNotifier(
            TelegramConfig(
                enabled=True,
                bot_token="secret-token",
                chat_id="123456",
            )
        )

        status = notifier.status()

        self.assertEqual(
            status,
            {
                "enabled": True,
                "configured": True,
                "ready": True,
                "token_configured": True,
                "chat_id_configured": True,
            },
        )
        self.assertNotIn("secret-token", str(status))
        self.assertNotIn("123456", str(status))

    def test_send_test_uses_fixed_message_and_configured_recipient(self) -> None:
        requests: list[tuple[str, dict, float]] = []

        def fake_poster(url: str, payload: dict, timeout: float) -> dict:
            requests.append((url, payload, timeout))
            return {"ok": True, "result": {"message_id": 42}}

        notifier = TelegramNotifier(
            TelegramConfig(
                enabled=False,
                bot_token="test-token",
                chat_id="-100123",
                timeout_seconds=4,
            ),
            poster=fake_poster,
        )

        result = notifier.send_test()

        self.assertTrue(result["sent"])
        self.assertEqual(result["message_id"], 42)
        self.assertEqual(requests[0][1]["chat_id"], "-100123")
        self.assertIn("No trading signals are enabled yet", requests[0][1]["text"])
        self.assertEqual(requests[0][2], 4)

    def test_environment_defaults_to_disabled(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "SB_TELEGRAM_ENABLED": "false",
                "SB_TELEGRAM_BOT_TOKEN": "",
                "SB_TELEGRAM_CHAT_ID": "",
            },
            clear=False,
        ):
            status = TelegramNotifier().status()

        self.assertFalse(status["enabled"])
        self.assertFalse(status["configured"])
        self.assertFalse(status["ready"])


class TelegramAPITests(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.pop(get_telegram_notifier, None)

    def test_status_endpoint_returns_safe_configuration_state(self) -> None:
        app.dependency_overrides[get_telegram_notifier] = lambda: _FakeNotifier()

        response = TestClient(app).get("/notifications/telegram/status")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["configured"])
        self.assertNotIn("bot_token", response.json())
        self.assertNotIn("chat_id", response.json())

    def test_test_endpoint_uses_notifier_without_live_request(self) -> None:
        fake = _FakeNotifier()
        app.dependency_overrides[get_telegram_notifier] = lambda: fake

        response = TestClient(app).post("/notifications/telegram/test")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message_id"], 77)
        self.assertEqual(fake.test_calls, 1)


class _FakeNotifier:
    def __init__(self) -> None:
        self.test_calls = 0

    def status(self) -> dict:
        return {
            "enabled": True,
            "configured": True,
            "ready": True,
            "token_configured": True,
            "chat_id_configured": True,
        }

    def send_test(self) -> dict:
        self.test_calls += 1
        return {
            **self.status(),
            "sent": True,
            "message_id": 77,
        }


if __name__ == "__main__":
    unittest.main()

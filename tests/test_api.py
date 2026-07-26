from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from sb_system.api import app


class APITests(unittest.TestCase):
    def test_vite_fallback_port_is_allowed_by_cors(self) -> None:
        response = TestClient(app).options(
            "/runtime/settings",
            headers={
                "Origin": "http://127.0.0.1:5175",
                "Access-Control-Request-Method": "PUT",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "http://127.0.0.1:5175",
        )


if __name__ == "__main__":
    unittest.main()

import importlib.util
from pathlib import Path
import unittest
import base64
import json
import os
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("collect", Path(__file__).resolve().parents[1] / "mods/usage-bar/collect.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class QuotaTests(unittest.TestCase):
    def test_codex_credits(self):
        for raw, expected in [("1234.50", "1234.5"), ("0", "0"), (15, "15")]:
            self.assertEqual(collector.parse_codex_credits({"credits": {"balance": raw}})["balance"], expected)
        for raw in ["secret-token", "NaN", "Infinity", "-1", True, "1e10000"]:
            self.assertIsNone(collector.parse_codex_credits({"credits": {"balance": raw}})["balance"])
        self.assertIsNone(collector.parse_codex_credits({}))
        self.assertTrue(collector.parse_codex_credits({"credits": {"unlimited": True}})["unlimited"])
        self.assertIsNone(collector.parse_codex_credits({"credits": {}})["has_credits"])

    def test_codex_credit_only_account(self):
        credits = {"balance": "25", "has_credits": True, "unlimited": False}
        with patch.object(collector, "codex", return_value={"windows": [], "credits": credits}):
            result = collector.collect("codex")
        self.assertIsNone(result["error"])
        self.assertEqual(result["credits"], credits)

    def test_codex_windows_and_zero(self):
        data = {"rate_limit": {"primary_window": {"used_percent": 0, "limit_window_seconds": 18000},
                               "secondary_window": {"used_percent": 47, "limit_window_seconds": 604800}}}
        self.assertEqual([(w["label"], w["used"]) for w in collector.parse_codex(data)], [("5h", 0), ("7d", 47)])

    def test_codex_monthly_is_not_mislabeled_weekly(self):
        result = collector.parse_codex({"rate_limit": {"primary_window": {"used_percent": 1, "limit_window_seconds": 2592000}}})
        self.assertEqual(result[0]["label"], "30d")

    def test_claude_missing_session_keeps_weekly(self):
        self.assertEqual(collector.parse_claude({"five_hour": None, "seven_day": {"utilization": 24}})[0]["label"], "7d")

    def test_cursor_prefers_reported_total_over_spend_estimate(self):
        result = collector.parse_cursor({"individualUsage": {"plan": {"totalPercentUsed": 73, "used": 10, "limit": 20}}})
        self.assertEqual(result[0]["used"], 73)

    def test_cursor_uses_ratio_only_when_total_missing(self):
        result = collector.parse_cursor({"individualUsage": {"plan": {"used": 3500, "limit": 2000}}})
        self.assertEqual(result[0]["used"], 175)

    def test_cursor_does_not_invent_unlimited_quota(self):
        self.assertEqual(collector.parse_cursor({"isUnlimited": True}), [])
        self.assertEqual(collector.parse_cursor({"individualUsage": {"plan": {"used": 0, "limit": 0}}}), [])

    def test_invalid_numbers_are_unavailable(self):
        for bad in [None, "45", True, -1, float("nan"), float("inf")]:
            self.assertIsNone(collector.window("Total", bad))

    def test_errors_do_not_expose_credentials(self):
        with patch.object(collector, "codex", side_effect=ValueError("Bearer secret-token")):
            result = collector.collect("codex")
        self.assertNotIn("secret-token", str(result))
        self.assertEqual(result["windows"], [])

    def test_provider_failures_stay_independent(self):
        with patch.object(collector, "claude", side_effect=collector.Unavailable("offline")), \
             patch.object(collector, "codex", return_value=[{"label": "5h", "used": 0, "reset": None}]):
            self.assertEqual(collector.collect("claude")["error"], "offline")
            self.assertIsNone(collector.collect("codex")["error"])

    def test_structured_errors_preserve_next_step(self):
        with patch.object(collector, "claude", side_effect=collector.Unavailable("No saved login", "not_signed_in", "Sign in with Claude Code")):
            result = collector.collect("claude")
        self.assertEqual(result["code"], "not_signed_in")
        self.assertEqual(result["action"], "Sign in with Claude Code")

    def test_cursor_cli_file_does_not_require_desktop_keychain(self):
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "auth0|test-user", "exp": time.time()+3600}).encode()).decode().rstrip("=")
        token = "header." + payload + ".signature"
        with patch.object(collector, "load_json", return_value={"accessToken": token}), \
             patch.object(collector, "keychain", side_effect=AssertionError("Keychain should not be used")):
            self.assertEqual(collector.cursor_token(), "test-user%3A%3A" + token)

    def test_browser_session_is_validated_and_saved_owner_only(self):
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "auth0|test-user", "exp": time.time()+3600}).encode()).decode().rstrip("=")
        cookie = "test-user%3A%3Aheader." + payload + ".signature"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"private/session.json"
            with patch.object(collector.sys, "platform", "darwin"), \
                 patch.object(collector, "session_path", return_value=path), \
                 patch.object(collector.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=cookie.encode())), \
                 patch.object(collector, "request", return_value={"individualUsage": {"plan": {"totalPercentUsed": 10}}}):
                collector.save_copied_session()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())["cookie"], cookie)

    def test_invalid_clipboard_is_never_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"session.json"
            with patch.object(collector.sys, "platform", "darwin"), \
                 patch.object(collector, "session_path", return_value=path), \
                 patch.object(collector.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=b"not a token")):
                result = collector.collect("cursor", copied_session=True)
            self.assertEqual(result["code"], "invalid_session")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

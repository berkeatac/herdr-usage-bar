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

    def test_cursor_shows_auto_and_other_models_separately(self):
        result = collector.parse_cursor({
            "billingCycleEnd": "2026-11-02T16:47:51.000Z",
            "individualUsage": {"plan": {
                "totalPercentUsed": 16.3, "used": 10, "limit": 20,
                "autoPercentUsed": 12.5, "apiPercentUsed": 0,
            }},
        })
        self.assertEqual([(w["label"], w["used"]) for w in result], [("Auto", 12.5), ("Other", 0)])
        self.assertEqual(result[0]["reset"], "2026-11-02T16:47:51.000Z")

    def test_cursor_current_period_overrides_stale_summary(self):
        result = collector.parse_cursor(
            {"billingCycleEnd": "2026-11-01T00:00:00.000Z",
             "individualUsage": {"plan": {"autoPercentUsed": 0, "apiPercentUsed": 0, "totalPercentUsed": 100}}},
            {"billingCycleEnd": "1792664856178",
             "planUsage": {"autoPercentUsed": 10.2, "apiPercentUsed": 1.5, "totalPercentUsed": 10.2}},
        )
        self.assertEqual([(w["label"], w["used"]) for w in result], [("Auto", 10.2), ("Other", 1.5)])
        self.assertEqual(result[0]["reset"], 1792664856.178)

    def test_cursor_invalid_pool_falls_back_per_field(self):
        result = collector.parse_cursor(
            {"individualUsage": {"plan": {"autoPercentUsed": 4, "apiPercentUsed": 2}}},
            {"planUsage": {"autoPercentUsed": "nope", "apiPercentUsed": 9}},
        )
        self.assertEqual([(w["label"], w["used"]) for w in result], [("Auto", 4), ("Other", 9)])

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


def http_error(code, headers=None):
    from email.message import Message
    import urllib.error
    message = Message()
    for name, value in (headers or {}).items():
        message[name] = value
    return urllib.error.HTTPError("https://example.invalid/usage", code, "error", message, None)


class RetryAfterTests(unittest.TestCase):
    def failure(self, code, headers=None):
        opener = SimpleNamespace(open=lambda *args, **kwargs: (_ for _ in ()).throw(http_error(code, headers)))
        with patch.object(collector.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(collector.Unavailable) as caught:
                collector.request("https://example.invalid/usage", {})
        return caught.exception

    def test_retry_after_seconds_and_dates(self):
        self.assertEqual(collector.retry_after({"Retry-After": "120"}), 120)
        when = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() + 600))
        self.assertAlmostEqual(collector.retry_after({"Retry-After": when}), 600, delta=5)
        past = time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time() - 600))
        self.assertEqual(collector.retry_after({"Retry-After": past}), 0)

    def test_retry_after_is_clamped_and_ignores_garbage(self):
        self.assertEqual(collector.retry_after({"Retry-After": "999999999"}), collector.RETRY_AFTER_MAX)
        self.assertIsNone(collector.retry_after({"Retry-After": "soon"}))
        self.assertIsNone(collector.retry_after({}))
        self.assertIsNone(collector.retry_after(None))

    def test_rate_limit_carries_retry_after(self):
        error = self.failure(429, {"Retry-After": "300"})
        self.assertEqual((error.code, error.retry_after), ("rate_limited", 300))

    def test_should_not_retry_waits_the_full_backoff(self):
        error = self.failure(429, {"x-should-retry": "false"})
        self.assertEqual(error.retry_after, collector.NO_RETRY_WAIT)

    def test_server_errors_are_transient(self):
        error = self.failure(503, {"Retry-After": "60"})
        self.assertEqual((error.code, error.retry_after), ("http_error", 60))

    def test_other_statuses_stay_non_transient(self):
        error = self.failure(404, {"Retry-After": "60"})
        self.assertEqual((error.code, error.retry_after), ("unavailable", None))

    def test_collect_reports_retry_after(self):
        with patch.object(collector, "claude", side_effect=collector.Unavailable("slow down", "rate_limited", None, 90)):
            self.assertEqual(collector.collect("claude")["retry_after"], 90)


if __name__ == "__main__":
    unittest.main()

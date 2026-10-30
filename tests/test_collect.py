import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("collect", Path(__file__).resolve().parents[1] / "mods/usage-bar/collect.py")
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class QuotaTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

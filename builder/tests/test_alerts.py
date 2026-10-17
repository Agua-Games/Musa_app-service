"""M4.4 tests: the SLO alert rules over serve JSONL logs."""

import json
import unittest

from musa_build.alerts import scan_log


def ev(**fields) -> str:
    base = {"ts": "2026-10-16T10:00:00.000+00:00", "level": "info",
            "tenant": "demo", "build": "b-1"}
    base.update(fields)
    return json.dumps(base)


class TestAlertRules(unittest.TestCase):
    def test_quiet_log_triggers_nothing(self):
        lines = [
            ev(event="api_request", method="GET", path="/collections", status=200),
            ev(event="assistant_ask", outcome="ok", cost_usd_estimate=0.0004),
            ev(event="api_request", method="GET", path="/assets/content/x/y.jpg", status=200),
            "not json at all",
            "{broken json",
        ]
        self.assertEqual(scan_log(lines), [])

    def test_assistant_cost_above_the_ceiling(self):
        lines = [ev(event="assistant_ask", outcome="ok", cost_usd_estimate=0.30),
                 ev(event="assistant_ask", outcome="ok", cost_usd_estimate=0.30)]
        alerts = scan_log(lines)  # 0.60 > 0.50 default
        self.assertEqual(len(alerts), 1)
        self.assertIn("custo do assistente", alerts[0])
        self.assertIn("0.6000", alerts[0])

    def test_quota_exceeded_always_alerts(self):
        lines = [ev(event="assistant_ask", outcome="quota_exceeded",
                    cost_usd_estimate=0.0)]
        alerts = scan_log(lines)
        self.assertEqual(len(alerts), 1)
        self.assertIn("cota diária", alerts[0])

    def test_rejected_cards_above_the_ceiling(self):
        lines = [ev(event="api_request", method="POST", path="/items", status=422)
                 for _ in range(11)]
        alerts = scan_log(lines)
        self.assertEqual(len(alerts), 1)
        self.assertIn("11 cards rejeitados", alerts[0])
        # a trickle of curator typos is normal — below the ceiling, no alert
        self.assertEqual(scan_log(lines[:10]), [])

    def test_asset_egress_above_the_band(self):
        lines = [ev(event="api_request", method="GET",
                    path="/assets/content/paintings/p1/img.jpg", status=200)
                 for _ in range(101)]
        alerts = scan_log(lines, assets_dia=100)
        self.assertEqual(len(alerts), 1)
        self.assertIn("101 downloads de assets", alerts[0])
        # 404s are not egress
        misses = [ev(event="api_request", method="GET",
                     path="/assets/content/paintings/p1/img.jpg", status=404)
                  for _ in range(101)]
        self.assertEqual(scan_log(misses, assets_dia=100), [])

    def test_any_5xx_alerts(self):
        lines = [ev(event="api_request", method="GET", path="/items/x", status=500)]
        alerts = scan_log(lines)
        self.assertEqual(len(alerts), 1)
        self.assertIn("5xx", alerts[0])

    def test_days_are_evaluated_separately(self):
        lines = [
            ev(ts="2026-10-15T23:00:00+00:00", event="assistant_ask",
               outcome="ok", cost_usd_estimate=0.40),
            ev(ts="2026-10-16T01:00:00+00:00", event="assistant_ask",
               outcome="ok", cost_usd_estimate=0.40),
        ]
        self.assertEqual(scan_log(lines), [])  # 0.40 per day, under the ceiling


if __name__ == "__main__":
    unittest.main()

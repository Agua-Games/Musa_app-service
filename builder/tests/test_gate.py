"""Gate semantics: fail closed, record reasons (M0.6)."""

import unittest

from musa_build.gate import gate_record, gate_status, gate_tier


class StatusGateTest(unittest.TestCase):
    def test_published_is_included(self):
        self.assertTrue(gate_status("published").included)

    def test_draft_is_excluded_with_reason(self):
        decision = gate_status("draft")
        self.assertFalse(decision.included)
        self.assertEqual(decision.reasons, ["website_status is 'draft'"])

    def test_missing_status_fails_closed(self):
        decision = gate_status(None)
        self.assertFalse(decision.included)
        self.assertIn("missing", decision.reasons[0])


class TierGateTest(unittest.TestCase):
    def test_bronze_item_reaches_every_museum(self):
        for tier in ("bronze", "silver", "gold"):
            self.assertTrue(gate_tier("bronze", tier).included)

    def test_gold_item_is_excluded_from_a_silver_museum(self):
        decision = gate_tier("gold", "silver")
        self.assertFalse(decision.included)
        self.assertIn("above the entitled tier", decision.reasons[0])

    def test_no_tier_means_bronze(self):
        self.assertTrue(gate_tier(None, "bronze").included)

    def test_unknown_tier_fails_closed(self):
        self.assertFalse(gate_tier("platinum", "gold").included)


class RecordGateTest(unittest.TestCase):
    def test_reasons_accumulate(self):
        decision = gate_record({"website_status": "draft", "tier": "gold"}, "bronze")
        self.assertFalse(decision.included)
        self.assertEqual(len(decision.reasons), 2)


if __name__ == "__main__":
    unittest.main()

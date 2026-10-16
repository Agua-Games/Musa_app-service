"""M4.3 tests: the gating audit (probe-by-probe proof, PT report)."""

import tempfile
import unittest
from pathlib import Path

from musa_build.audit import main as audit_main
from musa_build.audit import render_markdown, run_gating_audit

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "client-ok"


class TestGatingAudit(unittest.TestCase):
    """The fixture museum is purpose-built for this: one draft (draft-one),
    one above-tier item (twin-one, gold over a silver entitlement) and two
    public items — the audit must prove all of them gated correctly."""

    @classmethod
    def setUpClass(cls):
        cls.audit = run_gating_audit(FIXTURE)

    def test_audit_passes(self):
        self.assertTrue(self.audit.ok,
                        f"vazamentos: {[c.vazamentos for c in self.audit.checks if not c.ok]}")

    def test_counts_match_the_fixture(self):
        self.assertEqual(self.audit.museum_id, "fixture-museum")
        self.assertEqual(self.audit.tier, "silver")
        self.assertEqual(self.audit.public_items, 2)
        self.assertEqual(self.audit.draft_items, 1)
        self.assertEqual(self.audit.above_tier_items, 1)

    def test_every_check_actually_probed(self):
        # A check with zero probes proves nothing — guard against silently
        # vacuous passes (each fixture category must be exercised).
        self.assertEqual(len(self.audit.checks), 6)
        for check in self.audit.checks:
            self.assertGreater(check.sondas, 0, f"verificação vazia: {check.key}")

    def test_positive_control_is_part_of_the_proof(self):
        keys = {c.key for c in self.audit.checks}
        self.assertIn("controle-positivo", keys)

    def test_report_is_plain_portuguese_and_complete(self):
        text = render_markdown(self.audit)
        self.assertIn("APROVADO", text)
        self.assertIn("O que este relatório prova", text)
        self.assertIn("fixture-museum", text)
        self.assertIn("silver", text)
        self.assertIn("tier", text)
        self.assertIn("Como reproduzir", text)
        for check in self.audit.checks:
            self.assertIn(check.titulo, text)

    def test_cli_writes_the_report_and_exits_zero(self):
        tmp = tempfile.TemporaryDirectory()
        out = Path(tmp.name) / "auditoria.md"
        code = audit_main(["--repo", str(FIXTURE), "--out", str(out)])
        self.assertEqual(code, 0)
        text = out.read_text(encoding="utf-8")
        self.assertIn("APROVADO", text)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()

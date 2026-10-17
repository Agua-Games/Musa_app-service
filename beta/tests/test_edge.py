"""M4.5 tests: the edge battery runs green against the fixture museum
(silver tier, dev pin, unsigned config) and every enumerated edge case
produces exactly one verdict, with the red line intact at the end.

Fixture-specific expectations (they flip to real checks against the signed
DemoMuseum): the tamper case and the CI-preflight case are recorded as gaps
here — the fixture config is unsigned and the fixture repo ships no
workflow."""

import random
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from beta.edge import EdgeRunner
from beta.harness import BUILDER_DIR, ServeHarness

FIXTURES = Path(__file__).resolve().parent.parent.parent / "builder" / "tests" / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
FRONTEND = Path(__file__).resolve().parent.parent.parent / "source"
TOKEN = "beta-edge-test-token"

EXPECTED_ACOES = {
    "unicode-emoji-rtl-roundtrip", "asset-id-limites", "vazio-vs-ausente",
    "data-iso-bce", "titulo-gigante-colecao", "draft-orfao-colecao",
    "hero-despublicado", "colecao-vazia-publicada", "rev-duas-escritas",
    "sem-rev-ultima-vence", "leituras-durante-escritas", "escrita-durante-build",
    "duplicata-asset-id", "build-destino-invalido", "ci-sem-secrets",
    "capa-20mb", "peso-inicial", "conteudo-sem-cdn", "primeiro-acesso",
    "sem-admin-token", "tier-downgrade-upgrade", "config-adulterado",
    "overlay-corrompido-e-reconstruido", "acervo-pre-existente-intacto",
}

# Cases that are gaps ON THE FIXTURE (signed config / real CI needed for the
# real check): orphan visibility is a permanent known gap.
EXPECTED_FIXTURE_GAPS = {"draft-orfao-colecao", "ci-sem-secrets", "config-adulterado"}


class EdgeBatteryTest(unittest.TestCase):
    def _run_battery(self):
        tmp = tempfile.mkdtemp(prefix="musa-edge-test-")
        harness = None
        try:
            root = Path(tmp)
            shutil.copytree(CLIENT_OK, root / "repo")
            harness = ServeHarness(root / "repo", root / "overlay", token=TOKEN,
                                   log_dir=root / "logs")
            client = harness.boot()
            self.assertIsNotNone(client, "initial boot failed")
            self.assertTrue(client.login("edge@demo", TOKEN).ok)
            runner = EdgeRunner(harness, client, random.Random("t:edge"), "te",
                                "silver", root / "repo", BUILDER_DIR, FRONTEND, root)
            return runner.run_all()
        finally:
            if harness is not None:
                harness.stop()
            for _ in range(10):
                try:
                    shutil.rmtree(tmp, ignore_errors=False)
                    break
                except PermissionError:
                    time.sleep(0.5)
            else:
                shutil.rmtree(tmp, ignore_errors=True)

    def test_every_edge_case_has_a_verdict_and_nothing_fails(self):
        events = self._run_battery()
        acoes = {e.acao for e in events}
        self.assertEqual(acoes, EXPECTED_ACOES,
                         f"missing: {EXPECTED_ACOES - acoes}; extra: {acoes - EXPECTED_ACOES}")
        falhas = [e for e in events if e.resultado == "falha"]
        self.assertEqual(falhas, [],
                         f"edge cases failing: {[(e.acao, e.detalhe) for e in falhas]}")
        reprovas = [e for e in events if e.veredito == "reprova"]
        self.assertEqual(reprovas, [],
                         f"edge cases reprovados: {[(e.acao, e.detalhe) for e in reprovas]}")

    def test_fixture_gaps_are_the_expected_ones(self):
        events = self._run_battery()
        gaps = {e.acao for e in events if e.resultado == "achado-gap"}
        self.assertEqual(gaps, EXPECTED_FIXTURE_GAPS,
                         f"unexpected gap set: {gaps}")

    def test_red_line_holds_after_the_battery(self):
        events = self._run_battery()
        red_line = [e for e in events if e.acao == "acervo-pre-existente-intacto"]
        self.assertEqual(len(red_line), 1)
        self.assertEqual(red_line[0].resultado, "passa", f"RED LINE: {red_line[0].detalhe}")
        self.assertTrue(all(i["ok"] for i in red_line[0].invariantes))


if __name__ == "__main__":
    unittest.main()

"""M3.1 tests: persona determinism, green run on the fixture museum, gap
classification. Invariant sanity proofs live in test_invariants_sanity.py
(M3.3)."""

import os
import random
import shutil
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path

import uvicorn

from beta.client import ApiClient
from beta.personas import KNOWN_GAPS, SCOPES, Persona

FIXTURES = Path(__file__).resolve().parent.parent.parent / "builder" / "tests" / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
TOKEN = "beta-test-token"


def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def running_server():
    """Boot the real API (uvicorn, in-thread) on a disposable copy of the
    fixture client — the same path run_beta uses against the DemoMuseum."""
    from musa_build.serve import create_app

    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    shutil.copytree(CLIENT_OK, root / "repo")
    old = os.environ.get("MUSA_ADMIN_TOKEN")
    os.environ["MUSA_ADMIN_TOKEN"] = TOKEN
    app = create_app(root / "repo", data_dir=root / "overlay")
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        client = ApiClient(base_url)
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                if client.health(timeout=1.5).ok:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            raise RuntimeError("serve did not come up")
        yield client
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.state.serve.store.close()
        if old is None:
            os.environ.pop("MUSA_ADMIN_TOKEN", None)
        else:
            os.environ["MUSA_ADMIN_TOKEN"] = old
        tmp.cleanup()


def run_all(client: ApiClient, seed: int, run_id: str) -> list:
    events = []
    for email, scopes in SCOPES.items():
        persona = Persona(email, client, random.Random(f"{seed}:{email}"), run_id, "silver")
        assert client.login(email, TOKEN).ok
        for cenario in scopes:
            getattr(persona, {"diaria": "daily", "semanal": "weekly",
                              "pontual": "punctual"}[cenario])()
        events.extend(persona.events)
    return events


class FullRunTest(unittest.TestCase):
    def test_green_run_all_routines(self):
        with running_server() as client:
            events = run_all(client, seed=42, run_id="t1")
        self.assertTrue(events, "no events recorded")
        reprovas = [e for e in events if e.veredito == "reprova"]
        self.assertEqual(reprovas, [],
                         f"unexpected failures: {[(e.acao, e.detalhe) for e in reprovas]}")
        # every routine ended with the invariant suite attached somewhere
        with_inv = [e for e in events if e.invariantes]
        self.assertTrue(with_inv, "no event carries invariant results")
        for e in with_inv:
            self.assertTrue(all(i["ok"] for i in e.invariantes))

    def test_expected_gaps_are_recorded_and_known(self):
        with running_server() as client:
            events = run_all(client, seed=42, run_id="t2")
        gaps = [e for e in events if e.resultado == "achado-gap"]
        gap_ids = {e.detalhe.split(":")[0] for e in gaps}
        self.assertEqual(gap_ids, set(KNOWN_GAPS),
                         f"gap ids diverge from the known list: {gap_ids}")

    def test_publish_flow_hides_draft_then_shows_published(self):
        with running_server() as client:
            events = run_all(client, seed=7, run_id="t3")
        publishes = [e for e in events if e.acao == "publicar-item"]
        self.assertGreaterEqual(len(publishes), 4)  # 2 per persona x 2 personas
        self.assertTrue(all(e.resultado == "ok" for e in publishes))

    def test_same_seed_same_action_sequence(self):
        def sequence(seed, run_id):
            with running_server() as client:
                return [(e.cenario, e.persona, e.acao, e.alvo, e.resultado)
                        for e in run_all(client, seed, run_id)]
        self.assertEqual(sequence(42, "a"), sequence(42, "b"))
        self.assertNotEqual(sequence(42, "a"), sequence(43, "c"))


class MisuseTest(unittest.TestCase):
    """M3.2: the 10 hostile scenarios against the fixture museum (silver
    tier). Divergences marked falha are the current known bugs — when a fix
    lands, flip the expectation here (these are the acceptance tests of the
    fixes)."""

    def _run(self):
        from beta.misuse import MisuseRunner
        with running_server() as client:
            assert client.login("misuse@demo", TOKEN).ok
            runner = MisuseRunner(client, random.Random("t:misuse"), "tm", "silver")
            return runner.run_all()

    def test_all_scenarios_recorded_and_red_line_holds(self):
        events = self._run()
        red_line = [e for e in events if e.cenario == "linha-vermelha"]
        self.assertEqual(len(red_line), 1)
        self.assertEqual(red_line[0].resultado, "ok",
                         f"RED LINE: {red_line[0].detalhe}")
        scenarios = {e.cenario for e in events} - {"linha-vermelha"}
        self.assertEqual(len(scenarios), 10, f"missing scenarios: {scenarios}")

    def test_stable_rejections(self):
        events = self._run()
        by = {}
        for e in events:
            by.setdefault(e.cenario, []).append(e)
        # missing required field -> 422 naming it
        self.assertEqual(by["campo-obrigatorio-ausente"][0].resultado, "ok")
        # forged token -> 401, public unchanged
        self.assertEqual(by["token-invalido"][0].resultado, "ok")
        # tier gate: above-tier vanishes, restored returns
        gate = [e for e in by["downgrade-tier"] if e.acao == "gate-no-downgrade"]
        self.assertEqual(gate[0].resultado, "ok")
        # upload scenarios hit the known API gap for now
        for cen in ("arquivo-grande", "mime-errado", "glb-corrompido", "upload-interrompido"):
            self.assertEqual(by[cen][0].resultado, "achado-gap", cen)

    def test_fixed_divergences_now_pass(self):
        """The three M3.2 findings were fixed (409 on duplicate create,
        data_iso guard, write lock + _rev optimistic concurrency). These were
        the acceptance tests of the fixes — they must stay green."""
        events = self._run()
        by = {}
        for e in events:
            by.setdefault(e.cenario, []).append(e)
        for cen in ("asset-id-duplicado", "data-invalida", "edicoes-concorrentes"):
            for e in by[cen]:
                self.assertEqual(e.resultado, "ok", f"{cen}/{e.acao}: {e.detalhe}")


if __name__ == "__main__":
    unittest.main()

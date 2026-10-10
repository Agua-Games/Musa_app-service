"""M3.1 tests: persona determinism, green run on the fixture museum, gap
classification, and the sanity proof that each fast invariant can fail."""

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
from beta import invariants as inv
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


class FakeClient:
    """Canned API answers to force invariant violations (sanity proofs)."""

    def __init__(self, collections, items_by_collection, item_status):
        self._cols = collections
        self._items = items_by_collection
        self._status = item_status

    class _Res:
        def __init__(self, status, body):
            self.status, self.body, self.latency_ms = status, body, 0.0
            self.ok = 200 <= status < 300

    def collections(self, auth=False):
        return self._Res(200, {"data": self._cols})

    def collection_items(self, cid, include_drafts=False, auth=False):
        return self._Res(200, {"data": self._items.get(cid, [])})

    def item(self, asset_id, auth=False):
        return self._Res(self._status.get(asset_id, 404), None)


class InvariantSanityTest(unittest.TestCase):
    """Each invariant is forced to fail once — an assertion that never fails
    in its own sanity test is not an assertion (M3_plano.md, M3.3)."""

    def test_draft_invariant_catches_a_leak(self):
        cols = [{"id": "paintings", "tier": "bronze"}]
        items = {"paintings": [{"asset_id": "secret", "website_status": "draft",
                                "titulo": "x", "colecao": "paintings"}]}
        client = FakeClient(cols, items, {"secret": 200})  # draft leaks publicly
        self.assertFalse(inv.check_no_drafts_in_public(client).ok)
        client_ok = FakeClient(cols, items, {"secret": 404})
        self.assertTrue(inv.check_no_drafts_in_public(client_ok).ok)

    def test_tier_invariant_catches_above_tier_item(self):
        cols = [{"id": "paintings", "tier": "bronze"}]
        items = {"paintings": [{"asset_id": "gold-piece", "website_status": "published",
                                "tier": "gold"}]}
        client = FakeClient(cols, items, {"gold-piece": 200})  # gold leaks on silver museum
        self.assertFalse(inv.check_tier_gate(client, "silver").ok)
        client_ok = FakeClient(cols, items, {"gold-piece": 404})
        self.assertTrue(inv.check_tier_gate(client_ok, "silver").ok)

    def test_contract_invariant_catches_invalid_card(self):
        cols = [{"id": "paintings", "tier": "bronze"}]
        good = {"asset_id": "ok-1", "titulo": "T", "colecao": "paintings",
                "website_status": "published"}
        bad = {"asset_id": "bad-1", "colecao": "paintings",
               "website_status": "published"}  # no titulo
        client = FakeClient(cols, {"paintings": [good, bad]}, {})
        result = inv.check_contract_valid(client)
        self.assertFalse(result.ok)
        self.assertIn("bad-1", result.detail)
        client_ok = FakeClient(cols, {"paintings": [good]}, {})
        self.assertTrue(inv.check_contract_valid(client_ok).ok)


if __name__ == "__main__":
    unittest.main()

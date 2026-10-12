"""M3.3 sanity proofs: every invariant is forced to fail once.

An assertion that never fails in its own sanity test is not an assertion
(M3_plano.md, M3.3). The three fast invariants are exercised against a
FakeClient with canned API answers; build-green is exercised with real
builds (a broken repo must be caught, the fixture museum must pass).
"""

import tempfile
import unittest
from pathlib import Path

from beta import invariants as inv

PLATFORM_ROOT = Path(__file__).resolve().parent.parent.parent
BUILDER_DIR = PLATFORM_ROOT / "builder"
FRONTEND_DIR = PLATFORM_ROOT / "source"
CLIENT_OK = BUILDER_DIR / "tests" / "fixtures" / "client-ok"


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
    """Each invariant is forced to fail once — and also observed passing,
    so a broken checker that always fails (or always passes) is caught too."""

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

    def test_build_green_invariant_catches_a_broken_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken-repo"
            broken.mkdir()  # no museum.config.json — the build must fail
            result = inv.check_build_green(broken, FRONTEND_DIR,
                                           Path(tmp) / "out-broken", BUILDER_DIR)
            self.assertFalse(result.ok)
            self.assertIn("build exit", result.detail)

            ok = inv.check_build_green(CLIENT_OK, FRONTEND_DIR,
                                       Path(tmp) / "out-ok", BUILDER_DIR)
            self.assertTrue(ok.ok, ok.detail)


if __name__ == "__main__":
    unittest.main()

"""Write-path tests for the dynamic API (M1.4 phase 2): token auth, SQLite
overlay persistence, fail-closed defaults and gating on every write."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from musa_build.serve import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
TOKEN = "test-token-123"


class WriteBase(unittest.TestCase):
    """Each test class runs against a COPY of the fixture repo + a throwaway
    data dir, so writes never touch the fixtures."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        root = Path(cls._tmp.name)
        cls.repo = root / "repo"
        shutil.copytree(CLIENT_OK, cls.repo)
        cls.data_dir = root / "data"
        cls._old_token = os.environ.get("MUSA_ADMIN_TOKEN")
        os.environ["MUSA_ADMIN_TOKEN"] = TOKEN
        cls.client = TestClient(create_app(cls.repo, data_dir=cls.data_dir))
        cls.auth = {"Authorization": f"Bearer {TOKEN}"}

    @classmethod
    def tearDownClass(cls):
        cls.client.app.state.serve.store.close()
        if cls._old_token is None:
            os.environ.pop("MUSA_ADMIN_TOKEN", None)
        else:
            os.environ["MUSA_ADMIN_TOKEN"] = cls._old_token
        cls._tmp.cleanup()


class AuthTest(WriteBase):
    def test_write_without_token_is_a_401(self):
        res = self.client.post("/items", json={"asset_id": "x"})
        self.assertEqual(res.status_code, 401)

    def test_write_with_wrong_token_is_a_401(self):
        res = self.client.post(
            "/items", json={"asset_id": "x"}, headers={"Authorization": "Bearer nope"}
        )
        self.assertEqual(res.status_code, 401)

    def test_login_with_the_tenant_token(self):
        res = self.client.post("/auth/login", json={"email": "curator@fixture.example", "password": TOKEN})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["token"], TOKEN)
        self.assertEqual(body["user"]["org"], "fixture-museum")

    def test_login_with_wrong_password_is_a_401(self):
        res = self.client.post("/auth/login", json={"email": "a@b.c", "password": "nope"})
        self.assertEqual(res.status_code, 401)

    def test_health_reports_writes_enabled(self):
        self.assertEqual(self.client.get("/health").json()["writes"], "enabled")


class NoTokenConfiguredTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old = os.environ.pop("MUSA_ADMIN_TOKEN", None)
        cls.client = TestClient(create_app(CLIENT_OK, data_dir=tempfile.mkdtemp()))

    @classmethod
    def tearDownClass(cls):
        if cls._old is not None:
            os.environ["MUSA_ADMIN_TOKEN"] = cls._old

    def test_writes_answer_503_when_no_token_is_configured(self):
        res = self.client.post("/items", json={"asset_id": "x"})
        self.assertEqual(res.status_code, 503)
        self.assertIn("MUSA_ADMIN_TOKEN", res.json()["detail"])

    def test_health_reports_writes_disabled(self):
        self.assertEqual(self.client.get("/health").json()["writes"], "disabled")

    def test_reads_still_work(self):
        self.assertEqual(self.client.get("/collections").status_code, 200)


class CollectionWriteTest(WriteBase):
    def test_create_collection(self):
        res = self.client.post(
            "/collections",
            json={"id": "fotografia", "title": "Fotografia", "description": "Fotos."},
            headers=self.auth,
        )
        self.assertEqual(res.status_code, 201)
        ids = {c["id"] for c in self.client.get("/collections").json()["data"]}
        self.assertIn("fotografia", ids)

    def test_create_collection_rejects_bad_slug(self):
        res = self.client.post("/collections", json={"id": "Fotografia!"}, headers=self.auth)
        self.assertEqual(res.status_code, 422)

    def test_create_collection_conflict(self):
        res = self.client.post("/collections", json={"id": "paintings"}, headers=self.auth)
        self.assertEqual(res.status_code, 409)


class ItemWriteTest(WriteBase):
    def _create(self, asset_id="obra-nova", **overrides):
        card = {
            "asset_id": asset_id,
            "titulo": "Obra Nova",
            "colecao": "paintings",
            "autor": "Artista Teste",
            "image": "https://example.com/obra.jpg",
        }
        card.update(overrides)
        return self.client.post("/items", json=card, headers=self.auth)

    def test_new_item_defaults_to_draft_and_stays_hidden(self):
        res = self._create("obra-rascunho")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["website_status"], "draft")
        # Fail closed: not on the public API...
        self.assertEqual(self.client.get("/items/obra-rascunho").status_code, 404)
        public_ids = {i["asset_id"] for i in self.client.get("/collections/paintings/items").json()["data"]}
        self.assertNotIn("obra-rascunho", public_ids)
        # ...but visible to the tenant admin.
        admin = self.client.get("/items/obra-rascunho", headers=self.auth)
        self.assertEqual(admin.status_code, 200)
        with_drafts = self.client.get(
            "/collections/paintings/items?include_drafts=1", headers=self.auth
        ).json()["data"]
        self.assertIn("obra-rascunho", {i["asset_id"] for i in with_drafts})

    def test_include_drafts_requires_the_token(self):
        res = self.client.get("/collections/paintings/items?include_drafts=1")
        self.assertEqual(res.status_code, 401)

    def test_publish_patch_makes_the_item_public(self):
        self._create("obra-publicada")
        res = self.client.post(
            "/items", json={"asset_id": "obra-publicada", "website_status": "published"}, headers=self.auth
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.get("/items/obra-publicada").status_code, 200)
        hits = {i["asset_id"] for i in self.client.get("/search", params={"q": "nova"}).json()["data"]}
        self.assertIn("obra-publicada", hits)

    def test_hero_patch(self):
        self._create("obra-hero", website_status="published")
        self.client.post("/items", json={"asset_id": "obra-hero", "hero": True}, headers=self.auth)
        self.assertTrue(self.client.get("/items/obra-hero").json()["data"]["hero"])

    def test_patch_cannot_move_an_item_between_collections(self):
        self.client.post(
            "/items", json={"asset_id": "painting-one", "colecao": "sculptures"}, headers=self.auth
        )
        item = self.client.get("/items/painting-one").json()["data"]
        self.assertEqual(item["colecao"], "paintings")

    def test_invalid_card_is_a_422(self):
        res = self.client.post(
            "/items", json={"asset_id": "sem-titulo", "colecao": "paintings"}, headers=self.auth
        )
        self.assertEqual(res.status_code, 422)

    def test_unknown_collection_is_a_422(self):
        res = self._create("obra-orfa", colecao="nao-existe")
        self.assertEqual(res.status_code, 422)

    def test_above_tier_write_stays_gated_out(self):
        # Created at gold on a silver museum: stored, visible to the admin,
        # never published.
        self._create("obra-ouro", titulo="Obra Ouro", tier="gold", website_status="published")
        self.assertEqual(self.client.get("/items/obra-ouro").status_code, 404)
        self.assertEqual(self.client.get("/items/obra-ouro", headers=self.auth).status_code, 404)

    def test_writes_persist_in_the_sqlite_overlay(self):
        self._create("obra-persistente", website_status="published")
        # A fresh app over the same data dir sees the overlay, not just the seed.
        try:
            again = TestClient(create_app(self.repo, data_dir=self.data_dir))
            self.assertEqual(again.get("/items/obra-persistente").status_code, 200)
        finally:
            again.app.state.serve.store.close()

    def test_seed_repo_is_not_modified_by_writes(self):
        self._create("obra-imutavel", website_status="published")
        self.assertFalse((self.repo / "content/paintings/obra-imutavel").exists())


if __name__ == "__main__":
    unittest.main()

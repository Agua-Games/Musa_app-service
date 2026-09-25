"""Dynamic collection API tests (M1.4, ADR 0008): ``musa-build serve`` must
answer the same shapes as the static API, with the same gating — a draft or an
above-tier record is a 404, and its assets are not downloadable."""

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from musa_build.serve import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"


class ServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(CLIENT_OK))

    def test_health(self):
        body = self.client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["museum"], "fixture-museum")

    def test_envelope_shape_matches_the_static_api(self):
        body = self.client.get("/collections").json()
        self.assertEqual(set(body), {"data", "meta"})
        self.assertEqual(body["meta"]["contract"], "schemas/card/v1/card.schema.json")
        self.assertEqual(body["meta"]["museum"], "fixture-museum")
        self.assertEqual(body["meta"]["count"], len(body["data"]))

    def test_schema_endpoint_serves_the_bundled_contract(self):
        served = self.client.get("/schema").json()
        bundled = json.loads(
            (Path(__file__).resolve().parent.parent / "musa_build" / "schemas" / "card.schema.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(served, bundled)

    def test_collections_list_only_included_collections(self):
        ids = {c["id"] for c in self.client.get("/collections").json()["data"]}
        self.assertEqual(ids, {"paintings", "sculptures"})

    def test_collection_items(self):
        body = self.client.get("/collections/paintings/items").json()
        self.assertEqual([i["asset_id"] for i in body["data"]], ["painting-one"])
        self.assertEqual(body["meta"]["count"], 1)

    def test_item_full_record(self):
        item = self.client.get("/items/painting-one").json()["data"]
        self.assertEqual(item["asset_id"], "painting-one")
        self.assertEqual(item["titulo"], "Painting One")

    def test_draft_item_is_a_404(self):
        self.assertEqual(self.client.get("/items/draft-one").status_code, 404)

    def test_above_tier_item_is_a_404(self):
        # twin-one is gold; the fixture museum is entitled to silver.
        self.assertEqual(self.client.get("/items/twin-one").status_code, 404)

    def test_item_image_points_at_the_served_asset_path(self):
        item = self.client.get("/items/painting-one").json()["data"]
        self.assertEqual(item["image"], "assets/content/paintings/painting-one/images/f1.jpg")

    def test_included_item_asset_is_served(self):
        res = self.client.get("/assets/content/paintings/painting-one/images/f1.jpg")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, (CLIENT_OK / "content/paintings/painting-one/images/f1.jpg").read_bytes())

    def test_draft_item_asset_is_never_served(self):
        self.assertEqual(
            self.client.get("/assets/content/paintings/draft-one/images/secret.jpg").status_code, 404
        )

    def test_record_files_are_never_served(self):
        self.assertEqual(
            self.client.get("/assets/content/paintings/painting-one/card.json").status_code, 404
        )

    def test_path_traversal_is_a_404(self):
        # TestClient normalizes "..", so assert against the raw outcome: the
        # museum.config.json must not be downloadable through the asset route.
        res = self.client.get("/assets/content/paintings/..%2F..%2Fmuseum.config.json")
        self.assertEqual(res.status_code, 404)

    def test_skin_asset_is_served(self):
        res = self.client.get("/assets/content/_skin/hero.jpg")
        self.assertEqual(res.status_code, 200)

    def test_search_matches_tokens(self):
        body = self.client.get("/search", params={"q": "painting"}).json()
        ids = {i["asset_id"] for i in body["data"]}
        self.assertIn("painting-one", ids)
        self.assertNotIn("draft-one", ids)  # the index only covers included items

    def test_search_without_query_returns_empty(self):
        body = self.client.get("/search").json()
        self.assertEqual(body["data"], [])
        self.assertEqual(body["meta"]["count"], 0)

    def test_unknown_collection_items_is_a_404(self):
        self.assertEqual(self.client.get("/collections/nope/items").status_code, 404)


if __name__ == "__main__":
    unittest.main()

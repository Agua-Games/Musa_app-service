"""Static collection API tests (M1.1): the builder emits the REST contract as
JSON files, already gated — a draft is not even a file on disk."""

import json
import tempfile
import unittest
from pathlib import Path

from musa_build import CONTRACT_VERSION
from musa_build.build import build_site

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
FRONTEND = FIXTURES / "frontend"


class StaticApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.report = build_site(CLIENT_OK, FRONTEND, cls.out)
        cls.api = cls.out / "api"

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def read(self, *parts):
        return json.loads((self.api.joinpath(*parts)).read_text(encoding="utf-8"))

    def test_envelope_shape(self):
        body = self.read("collections.json")
        self.assertEqual(set(body), {"data", "meta"})
        self.assertEqual(body["meta"]["contract"], "schemas/card/v1/card.schema.json")
        self.assertEqual(body["meta"]["museum"], "fixture-museum")
        self.assertEqual(body["meta"]["count"], len(body["data"]))

    def test_schema_endpoint_serves_the_bundled_contract(self):
        served = self.read("schema.json")
        bundled = json.loads(
            (Path(__file__).resolve().parent.parent / "musa_build" / "schemas" / "card.schema.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(served, bundled)
        self.assertEqual(served["x-contract-version"], CONTRACT_VERSION)

    def test_collections_list_only_included_collections(self):
        ids = {c["id"] for c in self.read("collections.json")["data"]}
        self.assertEqual(ids, {"paintings", "sculptures"})

    def test_collection_items_endpoint(self):
        items = self.read("collections", "paintings", "items.json")
        self.assertEqual([i["asset_id"] for i in items["data"]], ["painting-one"])
        self.assertEqual(items["meta"]["count"], 1)

    def test_item_endpoint_serves_the_full_record(self):
        item = self.read("items", "painting-one.json")["data"]
        self.assertEqual(item["asset_id"], "painting-one")
        self.assertEqual(item["titulo"], "Painting One")
        self.assertEqual(item["image"], "assets/content/paintings/painting-one/images/f1.jpg")

    def test_gated_records_are_not_even_files(self):
        # draft-one is a draft; twin-one is above the entitled tier (gold in a
        # silver museum). The static API inherits the build gate: no file exists.
        self.assertFalse((self.api / "items" / "draft-one.json").exists())
        self.assertFalse((self.api / "items" / "twin-one.json").exists())
        raw_index = (self.api / "search.json").read_text(encoding="utf-8")
        self.assertNotIn("draft-one", raw_index)
        self.assertNotIn("twin-one", raw_index)

    def test_search_index_resolves_terms_to_items(self):
        index = self.read("search.json")["data"]
        self.assertEqual(index["terms"]["painting"], ["painting-one"])
        self.assertEqual(index["terms"]["statue"], ["statue-one"])
        self.assertIn("fixture", index["terms"])  # tags are indexed
        summary = index["items"]["statue-one"]
        self.assertEqual(summary["colecao"], "sculptures")
        self.assertNotIn("descricao", summary)  # slim records stay slim

    def test_runtime_config_points_the_frontend_at_the_static_api(self):
        runtime = (self.out / "data" / "runtime.js").read_text(encoding="utf-8")
        self.assertIn('mode: "live"', runtime)
        self.assertIn('static: true', runtime)


if __name__ == "__main__":
    unittest.main()

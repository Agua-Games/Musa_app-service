"""Semantic search acceptance test (M2.5 verification, run with the pipeline venv):

    .venv/Scripts/python.exe -m unittest test_semantic -v

The milestone criterion is stated against the DemoMuseum specifically, so this
test targets the sibling checkout and skips cleanly when it is absent.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLATFORM = ROOT.parent
DEMO = PLATFORM.parent / "DemoMuseum"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PLATFORM))

from build_vector_index import build_index, index_path  # noqa: E402
from mcp_server.tools import MusaRepo, search_semantic  # noqa: E402


@unittest.skipUnless((DEMO / "museum.config.json").is_file(), "DemoMuseum checkout not found")
class SemanticSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_index(DEMO)  # derived data: rebuild fresh every test run
        cls.repo = MusaRepo(DEMO)

    def test_index_covers_published_items(self):
        import sqlite3

        db = sqlite3.connect(index_path(DEMO))
        count = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        db.close()
        self.assertEqual(count, 13)  # 14 cards minus the intentional draft

    def test_pt_br_query_without_exact_card_words(self):
        # Plan criterion: 'retrato de moça holandesa' -> pearl earring in top-3.
        hits = search_semantic(self.repo, "retrato de moça holandesa", limit=3)
        ids = [h["asset_id"] for h in hits["results"]]
        self.assertIn("moca-com-brinco-de-perola", ids)

    def test_hits_are_traceable(self):
        hits = search_semantic(self.repo, "escultura egípcia antiga", limit=3)
        self.assertEqual(hits["results"][0]["asset_id"], "estatua-taweret")
        for hit in hits["results"]:
            self.assertIn(f"asset_id:{hit['asset_id']}", hit["sources"])
            self.assertTrue(any(s.startswith("content/") for s in hit["sources"]))


if __name__ == "__main__":
    unittest.main()

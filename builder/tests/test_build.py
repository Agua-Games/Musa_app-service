"""End-to-end build tests over the fixture client (M0 exit criteria, locally)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from musa_build.build import BuildFailure, build_site

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
FRONTEND = FIXTURES / "frontend"


class BuildOkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.report = build_site(CLIENT_OK, FRONTEND, cls.out)
        cls.catalog = json.loads((cls.out / "data" / "catalog.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def item_ids(self):
        return {item["asset_id"] for item in self.catalog["items"]}

    def test_report_is_successful(self):
        self.assertTrue(self.report.ok, self.report.errors)

    def test_draft_never_reaches_the_payload(self):
        self.assertNotIn("draft-one", self.item_ids())
        raw = (self.out / "data" / "catalog.js").read_text(encoding="utf-8")
        self.assertNotIn("draft-one", raw)
        # and neither do its bytes
        self.assertFalse((self.out / "assets" / "content" / "paintings" / "draft-one").exists())

    def test_item_above_the_entitled_tier_is_excluded(self):
        self.assertNotIn("twin-one", self.item_ids())  # gold item, silver museum

    def test_published_items_are_included(self):
        self.assertEqual(self.item_ids(), {"painting-one", "statue-one"})

    def test_exclusions_carry_a_one_line_reason(self):
        reasons = {e.ref: e.reasons for e in self.report.entries if not e.included}
        self.assertIn("website_status is 'draft'", reasons["draft-one"][0])
        self.assertIn("above the entitled tier", reasons["twin-one"][0])

    def test_assets_are_copied_and_paths_rewritten(self):
        item = next(i for i in self.catalog["items"] if i["asset_id"] == "painting-one")
        self.assertEqual(item["image"], "assets/content/paintings/painting-one/images/f1.jpg")
        self.assertTrue((self.out / item["image"]).is_file())
        statue = next(i for i in self.catalog["items"] if i["asset_id"] == "statue-one")
        self.assertTrue((self.out / statue["model_primary"]).is_file())

    def test_frontend_is_copied_without_demo_content_or_dev_files(self):
        self.assertTrue((self.out / "index.html").is_file())
        self.assertTrue((self.out / "assets" / "js" / "app.js").is_file())
        self.assertFalse((self.out / "server.mjs").exists())
        self.assertFalse((self.out / "assets" / "img").exists())  # demo imagery stays out

    def test_museum_identity_and_skin_come_from_the_config(self):
        museum = self.catalog["museum"]
        self.assertEqual(museum["id"], "fixture-museum")
        self.assertEqual(museum["tier"], "silver")
        self.assertEqual(museum["skin"]["hero"], "assets/content/_skin/hero.jpg")
        self.assertTrue((self.out / "assets" / "content" / "_skin" / "hero.jpg").is_file())

    def test_platform_owned_plans_are_bundled(self):
        self.assertIn("tiers", self.catalog["plans"])

    def test_build_report_files_exist(self):
        self.assertTrue((self.out / "build-report.json").is_file())
        md = (self.out / "build-report.md").read_text(encoding="utf-8")
        self.assertIn("EXCLUDED", md)
        self.assertIn("draft-one", md)

    def test_dotfiles_never_reach_the_payload(self):
        # client repos carry .gitkeep etc.; those are repo plumbing, not content
        self.assertFalse(
            (self.out / "assets" / "content" / "paintings" / "painting-one" / ".gitkeep").exists()
        )


class BuildFailureTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _copy_client(self) -> Path:
        repo = self.tmp / "client"
        shutil.copytree(CLIENT_OK, repo)
        return repo

    def test_a_corrupted_card_fails_the_build(self):
        repo = self._copy_client()
        card = repo / "content" / "paintings" / "painting-one" / "card.json"
        data = json.loads(card.read_text(encoding="utf-8"))
        del data["titulo"]
        card.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(BuildFailure) as ctx:
            build_site(repo, FRONTEND, self.tmp / "site")
        self.assertTrue(any("titulo" in e for e in ctx.exception.report.errors))

    def test_a_wrong_version_pin_fails_the_build(self):
        repo = self._copy_client()
        config = json.loads((repo / "museum.config.json").read_text(encoding="utf-8"))
        config["musa"] = "0.0.0-ancient"
        (repo / "museum.config.json").write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(BuildFailure) as ctx:
            build_site(repo, FRONTEND, self.tmp / "site")
        self.assertTrue(any("pins musa" in e for e in ctx.exception.report.errors))

    def test_folder_identity_mismatch_fails_the_build(self):
        repo = self._copy_client()
        card = repo / "content" / "paintings" / "painting-one" / "card.json"
        data = json.loads(card.read_text(encoding="utf-8"))
        data["colecao"] = "elsewhere"
        card.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(BuildFailure) as ctx:
            build_site(repo, FRONTEND, self.tmp / "site")
        self.assertTrue(any("colecao" in e for e in ctx.exception.report.errors))


if __name__ == "__main__":
    unittest.main()

"""Asset upload + remote-asset gate tests (M1.3): cards are rewritten to public
URLs, binaries go to the bucket (fake S3), and the build refuses to publish an
asset URL that does not answer HEAD 200."""

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from musa_build.build import BuildFailure, build_site
from musa_build.upload import upload_assets

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
FRONTEND = FIXTURES / "frontend"
BASE_URL = "https://pub-test.r2.dev"


class FakeS3:
    """Records puts; answers like a bucket."""

    def __init__(self):
        self.objects = {}

    def put_object(self, *, Bucket, Key, Body, ContentType, CacheControl):
        self.objects[(Bucket, Key)] = {"body": Body, "content_type": ContentType}


class UploadBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.repo = Path(cls._tmp.name) / "repo"
        shutil.copytree(CLIENT_OK, cls.repo)
        # The fixture config has only assetsBaseUrl; upload needs the full block.
        config_path = cls.repo / "museum.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["storage"] = {
            "provider": "r2",
            "bucket": "musa-assets-fixture",
            "endpoint": "https://account.r2.cloudflarestorage.com",
            "assetsBaseUrl": BASE_URL,
        }
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        cls.s3 = FakeS3()
        cls.report = upload_assets(cls.repo, s3=cls.s3)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def card(self, *parts):
        return json.loads(self.repo.joinpath("content", *parts).read_text(encoding="utf-8"))


class UploadTest(UploadBase):
    def test_local_image_is_uploaded_and_card_rewritten(self):
        card = self.card("paintings", "painting-one", "card.json")
        self.assertEqual(card["image"], f"{BASE_URL}/paintings/painting-one/images/f1.jpg")
        self.assertIn(("musa-assets-fixture", "paintings/painting-one/images/f1.jpg"), self.s3.objects)

    def test_local_model_is_uploaded(self):
        card = self.card("sculptures", "statue-one", "card.json")
        self.assertEqual(card["model_primary"], f"{BASE_URL}/sculptures/statue-one/models/e1.glb")

    def test_upload_is_not_a_gate_decision(self):
        # Drafts get their assets uploaded too — gating stays a build concern.
        card = self.card("paintings", "draft-one", "card.json")
        self.assertTrue(card["image"].startswith(BASE_URL))

    def test_item_without_local_assets_is_untouched(self):
        card = self.card("sculptures", "twin-one", "card.json")
        self.assertNotIn("model_primary", card)

    def test_uploaded_files_keep_their_bytes(self):
        original = (CLIENT_OK / "content/paintings/painting-one/images/f1.jpg").read_bytes()
        stored = self.s3.objects[("musa-assets-fixture", "paintings/painting-one/images/f1.jpg")]
        self.assertEqual(stored["body"], original)

    def test_rewritten_card_stays_valid_json_with_utf8(self):
        text = self.repo.joinpath("content/sculptures/statue-one/card.json").read_text(encoding="utf-8")
        json.loads(text)  # must parse

    def test_second_run_is_a_noop(self):
        s3_again = FakeS3()
        upload_assets(self.repo, s3=s3_again)
        self.assertEqual(s3_again.objects, {})  # everything is a URL already


class UploadConfigTest(unittest.TestCase):
    def test_missing_storage_block_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            shutil.copytree(CLIENT_OK, repo)  # fixture lacks bucket/endpoint
            with self.assertRaises(BuildFailure) as ctx:
                upload_assets(repo, s3=FakeS3())
            self.assertIn("storage.bucket", "; ".join(ctx.exception.report.errors))


def _build_with_url_item(tmp: Path, url: str):
    """Fixture copy whose one published item references a REMOTE asset URL."""
    repo = tmp / "repo"
    shutil.copytree(CLIENT_OK, repo)
    config_path = repo / "museum.config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["storage"] = {"assetsBaseUrl": BASE_URL}
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    card_path = repo / "content/paintings/painting-one/card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    card["image"] = url
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return repo


class _FakeResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class RemoteAssetGateTest(unittest.TestCase):
    def test_build_fails_when_bucket_asset_does_not_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _build_with_url_item(Path(tmp), f"{BASE_URL}/paintings/painting-one/images/f1.jpg")
            with mock.patch("musa_build.build.urllib.request.urlopen",
                            side_effect=OSError("404")):
                with self.assertRaises(BuildFailure) as ctx:
                    build_site(repo, FRONTEND, Path(tmp) / "out")
            self.assertIn("not reachable", "; ".join(ctx.exception.report.errors))

    def test_build_passes_when_bucket_asset_answers_200(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _build_with_url_item(Path(tmp), f"{BASE_URL}/paintings/painting-one/images/f1.jpg")
            with mock.patch("musa_build.build.urllib.request.urlopen",
                            return_value=_FakeResponse(200)) as head:
                report = build_site(repo, FRONTEND, Path(tmp) / "out")
            self.assertTrue(report.ok)
            self.assertTrue(head.called)

    def test_external_urls_are_not_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _build_with_url_item(Path(tmp), "https://upload.wikimedia.org/x.jpg")
            with mock.patch("musa_build.build.urllib.request.urlopen") as head:
                report = build_site(repo, FRONTEND, Path(tmp) / "out")
            self.assertTrue(report.ok)
            head.assert_not_called()

    def test_draft_assets_are_not_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = _build_with_url_item(Path(tmp), f"{BASE_URL}/ok.jpg")
            # Point the DRAFT at a broken bucket URL; the build must not care.
            draft_path = repo / "content/paintings/draft-one/card.json"
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            draft["image"] = f"{BASE_URL}/not-uploaded-yet.jpg"
            draft_path.write_text(json.dumps(draft, indent=2), encoding="utf-8")
            with mock.patch("musa_build.build.urllib.request.urlopen",
                            return_value=_FakeResponse(200)) as head:
                report = build_site(repo, FRONTEND, Path(tmp) / "out")
            self.assertTrue(report.ok)
            self.assertEqual(head.call_count, 1)  # only the published item's URL


if __name__ == "__main__":
    unittest.main()

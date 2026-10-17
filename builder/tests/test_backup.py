"""M4.4 tests: overlay backup + restore — the DR mechanics the drill times."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from musa_build.backup import BackupError, create_backup, restore_backup, main
from musa_build.serve import create_app

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
TOKEN = "backup-test-token"


def public_payload(client: TestClient) -> dict:
    """Canonical snapshot of everything public, for before/after comparison."""
    cols = client.get("/collections").json()["data"]
    items = {}
    for col in cols:
        for slim in client.get(f"/collections/{col['id']}/items").json()["data"]:
            items[slim["asset_id"]] = client.get(f"/items/{slim['asset_id']}").json()["data"]
    return json.loads(json.dumps({"collections": cols, "items": items},
                                 sort_keys=True, ensure_ascii=False))


class BackupRoundTripTest(unittest.TestCase):
    """Write via the API (overlay-only edits), back up, DESTROY the overlay,
    restore, and prove the public payload is byte-identical."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.repo = root / "repo"
        shutil.copytree(CLIENT_OK, self.repo)
        self.data_dir = root / "overlay"
        self.backups = root / "backups"
        self._old = os.environ.get("MUSA_ADMIN_TOKEN")
        os.environ["MUSA_ADMIN_TOKEN"] = TOKEN

    def tearDown(self):
        if self._old is None:
            os.environ.pop("MUSA_ADMIN_TOKEN", None)
        else:
            os.environ["MUSA_ADMIN_TOKEN"] = self._old
        self._tmp.cleanup()

    def _client(self) -> TestClient:
        return TestClient(create_app(self.repo, data_dir=self.data_dir))

    def _write_some_edits(self, client: TestClient) -> None:
        auth = {"Authorization": f"Bearer {TOKEN}"}
        assert client.post("/collections",
                           json={"id": "backup-col", "title": "Coleção Backup"},
                           headers=auth).status_code == 201
        card = {
            "asset_id": "backup-item", "titulo": "Peça do Backup",
            "colecao": "backup-col", "autor": "Curador", "data": "2026",
            "material": "Digital", "descricao": "Existe só no overlay.",
            "website_status": "published",
        }
        assert client.post("/items", json=card, headers=auth).status_code == 200

    def test_round_trip_byte_identical(self):
        client = self._client()
        self._write_some_edits(client)
        before = public_payload(client)
        client.app.state.serve.store.close()

        backup_dir = create_backup(self.repo, data_dir=self.data_dir,
                                   out_dir=self.backups)
        manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["museum_id"], "fixture-museum")
        self.assertEqual(manifest["counts"], {"items": 1, "collections": 1})

        # the disaster: the whole overlay is gone
        shutil.rmtree(self.data_dir)

        result = restore_backup(self.repo, backup_dir=backup_dir,
                                data_dir=self.data_dir)
        self.assertEqual(result["total_items"], 5)  # 4 seed + 1 overlay

        after_client = self._client()
        after = public_payload(after_client)
        after_client.app.state.serve.store.close()
        self.assertEqual(before, after)

    def test_restore_moves_the_existing_overlay_aside(self):
        client = self._client()
        self._write_some_edits(client)
        client.app.state.serve.store.close()
        backup_dir = create_backup(self.repo, data_dir=self.data_dir,
                                   out_dir=self.backups)
        # a NEWER edit lands after the backup — restore must not destroy it
        client = self._client()
        auth = {"Authorization": f"Bearer {TOKEN}"}
        client.post("/items", json={"asset_id": "backup-item",
                                    "descricao": "edição posterior ao backup"},
                    headers=auth)
        client.app.state.serve.store.close()

        restore_backup(self.repo, backup_dir=backup_dir, data_dir=self.data_dir)
        asides = list(self.data_dir.glob("state.before-restore-*"))
        self.assertEqual(len(asides), 1, "o overlay atual não foi preservado")

    def test_backup_without_overlay_fails_cleanly(self):
        with self.assertRaises(BackupError):
            create_backup(self.repo, data_dir=self.data_dir, out_dir=self.backups)

    def test_restore_refuses_the_wrong_museum(self):
        client = self._client()
        self._write_some_edits(client)
        client.app.state.serve.store.close()
        backup_dir = create_backup(self.repo, data_dir=self.data_dir,
                                   out_dir=self.backups)
        config_path = self.repo / "museum.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["museum"]["id"] = "outro-museu"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(BackupError) as ctx:
            restore_backup(self.repo, backup_dir=backup_dir, data_dir=self.data_dir)
        self.assertIn("wrong tenant", str(ctx.exception))

    def test_restore_refuses_a_corrupted_copy(self):
        client = self._client()
        self._write_some_edits(client)
        client.app.state.serve.store.close()
        backup_dir = create_backup(self.repo, data_dir=self.data_dir,
                                   out_dir=self.backups)
        db = backup_dir / "state.db"
        data = bytearray(db.read_bytes())
        data[len(data) // 2] ^= 0xFF  # flip one byte in the middle
        db.write_bytes(bytes(data))
        with self.assertRaises(BackupError) as ctx:
            restore_backup(self.repo, backup_dir=backup_dir, data_dir=self.data_dir)
        self.assertIn("sha256", str(ctx.exception))

    def test_cli_exit_codes(self):
        client = self._client()
        self._write_some_edits(client)
        client.app.state.serve.store.close()
        code = main(["backup", "--repo", str(self.repo),
                     "--data-dir", str(self.data_dir), "--out", str(self.backups)])
        self.assertEqual(code, 0)
        backups = list(self.backups.iterdir())
        self.assertEqual(len(backups), 1)
        code = main(["restore", "--repo", str(self.repo),
                     "--data-dir", str(self.data_dir), "--from", str(backups[0])])
        self.assertEqual(code, 0)
        code = main(["restore", "--repo", str(self.repo),
                     "--data-dir", str(self.data_dir), "--from", str(self.backups)])
        self.assertEqual(code, 2)  # not a backup directory


if __name__ == "__main__":
    unittest.main()

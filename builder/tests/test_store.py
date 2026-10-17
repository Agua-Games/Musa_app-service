"""Store overlay edge cases (M4.5): a corrupted database fails EXPLICITLY
with the operator path in the message — never a silently empty museum."""

import tempfile
import unittest
from pathlib import Path

from musa_build.store import Store, StoreError


class TestStoreOverlay(unittest.TestCase):
    def test_corrupted_database_raises_explicit_store_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "state.db").write_bytes(b"this is not a sqlite database at all")
            with self.assertRaises(StoreError) as ctx:
                Store(data_dir)
            message = str(ctx.exception)
            self.assertIn("overlay database is unreadable", message)
            self.assertIn("musa-build restore", message)  # the operator path

    def test_fresh_directory_bootstraps_an_empty_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            try:
                self.assertEqual(store.load_items(), [])
                self.assertEqual(store.load_collections(), [])
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()

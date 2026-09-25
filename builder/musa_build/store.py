"""Per-instance write store (ADR 0008, M1.4 phase 2): a small SQLite overlay.

The client repository remains the *seed* (versioned, auditable). Day-to-day
edits made through the API — new collections, new items, publish/hero patches —
live in one SQLite file per deployed instance. On startup the server loads the
seed and applies the overlay on top: a record present in both is the database
version, a record only in the database is an addition made via the API.

The file lives OUTSIDE the repository's tracked content by default
(``<repo>/.musa/state.db`` — clients gitignore ``.musa/``), so admin edits
never dirty the client's git history.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    meta_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    collection_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    card_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, asset_id)
);
"""


class Store:
    """Thread-safe-ish SQLite overlay (one writer per instance)."""

    def __init__(self, data_dir: Path):
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "state.db"
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def load_collections(self) -> list[dict]:
        rows = self._db.execute("SELECT meta_json FROM collections ORDER BY rowid").fetchall()
        return [json.loads(row[0]) for row in rows]

    def load_items(self) -> list[dict]:
        rows = self._db.execute("SELECT card_json FROM items ORDER BY rowid").fetchall()
        return [json.loads(row[0]) for row in rows]

    def upsert_collection(self, meta: dict) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO collections (id, meta_json, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT (id) DO UPDATE SET meta_json = excluded.meta_json, "
                "updated_at = excluded.updated_at",
                (meta["id"], json.dumps(meta, ensure_ascii=False), self._now()),
            )

    def upsert_item(self, card: dict) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO items (collection_id, asset_id, card_json, updated_at) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT (collection_id, asset_id) DO UPDATE SET "
                "card_json = excluded.card_json, updated_at = excluded.updated_at",
                (
                    card["colecao"],
                    card["asset_id"],
                    json.dumps(card, ensure_ascii=False),
                    self._now(),
                ),
            )

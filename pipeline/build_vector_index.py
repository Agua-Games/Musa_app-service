"""Build the per-museum sqlite-vec index from a client repo's cards (M2.5, ADR 0013).

The index is DERIVED data — the cards are the source of truth, and this file can
be deleted and rebuilt at any time. It lives in the serve overlay directory
(<repo>/.musa/vec.db), which is gitignored everywhere.

Usage (pipeline venv python):
    .venv/Scripts/python.exe build_vector_index.py --repo ../../DemoMuseum
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import sqlite_vec

sys.path.insert(0, str(Path(__file__).resolve().parent))  # embeddings.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "builder"))

from embeddings import DIMENSIONS, embed, item_text  # noqa: E402
from musa_build.build import read_content  # noqa: E402
from musa_build.report import BuildReport  # noqa: E402

INDEX_NAME = "vec.db"


def index_path(repo: Path) -> Path:
    return Path(repo) / ".musa" / INDEX_NAME


def build_index(repo: Path) -> dict:
    repo = Path(repo)
    report = BuildReport(museum_id="vector-index", builder_version="pipeline",
                         contract_version="v1", entitled_tier="gold")
    collections, items, _site = read_content(repo, report)
    cards = [i for i in items if i.get("website_status") == "published"]
    if not cards:
        raise RuntimeError(f"no published items in {repo}")

    db_path = index_path(repo)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # derived data: rebuild from scratch

    db = sqlite3.connect(db_path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.execute("CREATE TABLE items(asset_id TEXT PRIMARY KEY, colecao TEXT, titulo TEXT, text TEXT)")
    db.execute(f"CREATE VIRTUAL TABLE vec_items USING vec0(embedding float[{DIMENSIONS}])")

    vectors = embed([item_text(c) for c in cards], kind="passage")
    for card, vector in zip(cards, vectors):
        cursor = db.execute(
            "INSERT INTO items(asset_id, colecao, titulo, text) VALUES (?, ?, ?, ?)",
            (card["asset_id"], card.get("colecao", ""), card.get("titulo", ""), item_text(card)),
        )
        db.execute("INSERT INTO vec_items(rowid, embedding) VALUES (?, ?)",
                   (cursor.lastrowid, vector.tobytes()))
    db.commit()
    count = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    db.close()
    return {"repo": str(repo), "index": str(db_path), "items": count}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    result = build_index(Path(args.repo))
    print(f"INDEX OK — {result['items']} item(s) embedded at {result['index']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

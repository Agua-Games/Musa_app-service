"""Import the structured batch into a client museum repo (M2.6).

Writes content/acervo-importado/<asset_id>/card.json per structured card —
metadata only, no binaries (owner's cost decision, 2026-10-08). Publication
rule, from the M2.4 finding: a card is born PUBLISHED only when every field
the review queue flags is tags (inferred by design, never blocks); any other
queued field keeps the card in draft for directed human review.

Usage:
    python import_to_museum.py --repo ../../DemoMuseum [--collection acervo-importado]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"

COLLECTION_META = {
    "title": "Acervo Importado (Pipeline M2)",
    "description": "450 fichas catalogadas pela pipeline OCR + LLM, medidas em docs/M2_resultados.md.",
    "tier": "bronze",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--collection", default="acervo-importado")
    args = parser.parse_args()

    repo = Path(args.repo)
    queue = json.loads((CORPUS / "review-queue.json").read_text(encoding="utf-8"))
    queued_by_card: dict[str, list[str]] = {}
    for entry in queue:
        queued_by_card.setdefault(entry["asset_id"], []).append(entry["field"])

    coll_dir = repo / "content" / args.collection
    coll_dir.mkdir(parents=True, exist_ok=True)
    (coll_dir / "collection.json").write_text(
        json.dumps(COLLECTION_META, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    published = drafted = 0
    for path in sorted((CORPUS / "structured").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["status"] != "ok":
            continue
        card = record["card"]
        card["colecao"] = args.collection
        blocking = [f for f in queued_by_card.get(card["asset_id"], []) if f != "tags"]
        card["website_status"] = "draft" if blocking else "published"
        item_dir = coll_dir / card["asset_id"]
        if item_dir.exists():
            print(f"  COLLISION {card['asset_id']} — skipped, never overwritten", file=sys.stderr)
            continue
        item_dir.mkdir(parents=True)
        (item_dir / "card.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if blocking:
            drafted += 1
        else:
            published += 1

    print(f"IMPORT OK — {published} published, {drafted} draft (review queue), "
          f"collection {args.collection} at {coll_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

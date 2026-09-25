"""Static collection API emission (ADR 0008, phase M1.1).

The builder emits the REST contract of spec §6.1 as plain JSON files, so the
frontend's ``live`` mode works against any static host today and against the
dynamic backend tomorrow — same shapes, same envelope, no view changes.

Emitted layout (gating already applied — only INCLUDED records exist here):

    api/schema.json                    the ficha contract, verbatim
    api/collections.json               envelope: list of collections
    api/collections/<id>/items.json    envelope: the collection's items
    api/items/<id>.json                envelope: one full record
    api/search.json                    envelope: precomputed term index + slim records

Envelope (every file except the schema):

    { "data": <payload>, "meta": { "contract", "generated", "museum", "count"? } }

Errors: a missing resource is a missing file — the host answers 404 and the
client maps it to "not found". Pagination: static mode serves full lists with
``meta.count``; cursor parameters are documented for the dynamic backend.
"""

import json
import re
from pathlib import Path

TOKEN_SPLIT = re.compile(r"[^\w]+", re.UNICODE)

# Fields the precomputed search index carries per item — enough to render a
# result card without a second request.
SUMMARY_FIELDS = ("asset_id", "colecao", "subcolecao", "titulo", "autor", "data", "image", "tier", "tags")

# Fields whose text feeds the term index.
INDEXED_FIELDS = ("titulo", "autor", "descricao", "material", "colecao", "subcolecao")


def _tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_SPLIT.split(text.lower()) if len(token) >= 2]


def _envelope(data, *, museum_id: str, generated: str, count: int | None = None) -> dict:
    meta = {
        "contract": "schemas/ficha/v1/ficha.schema.json",
        "generated": generated,
        "museum": museum_id,
    }
    if count is not None:
        meta["count"] = count
    return {"data": data, "meta": meta}


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_search_index(items: list[dict]) -> dict:
    """Precomputed term index: token -> [asset_id], plus slim records by id."""
    terms: dict[str, set[str]] = {}
    summaries: dict[str, dict] = {}
    for item in items:
        asset_id = item["asset_id"]
        summaries[asset_id] = {k: v for k, v in item.items() if k in SUMMARY_FIELDS and v is not None}
        text = " ".join(str(item.get(field) or "") for field in INDEXED_FIELDS)
        text += " " + " ".join(item.get("tags") or [])
        for token in set(_tokenize(text)):
            terms.setdefault(token, set()).add(asset_id)
    return {
        "terms": {token: sorted(ids) for token, ids in sorted(terms.items())},
        "items": summaries,
    }


def emit_api(out: Path, *, museum_id: str, generated: str, collections: list[dict], items: list[dict]) -> None:
    """Write the static API into ``out/api/``. Input records are already gated."""
    api = Path(out) / "api"
    meta = {"museum_id": museum_id, "generated": generated}

    schema_src = Path(__file__).parent / "schemas" / "ficha.schema.json"
    _write(api / "schema.json", json.loads(schema_src.read_text(encoding="utf-8")))

    _write(api / "collections.json", _envelope(collections, **meta, count=len(collections)))

    for collection in collections:
        collection_items = [item for item in items if item.get("colecao") == collection["id"]]
        _write(
            api / "collections" / collection["id"] / "items.json",
            _envelope(collection_items, **meta, count=len(collection_items)),
        )

    for item in items:
        _write(api / "items" / f"{item['asset_id']}.json", _envelope(item, **meta))

    _write(api / "search.json", _envelope(build_search_index(items), **meta, count=len(items)))

"""Dynamic collection API (ADR 0008, phase M1.4): ``musa-build serve``.

Same shapes, envelope and gating as the static API (api.py) — the frontend's
``live`` mode talks to this server exactly as it talks to the emitted JSON
files, so switching static <-> dynamic is a ``baseUrl`` change, never a view
change (see source/assets/js/api.js).

Phase 1 is read-only: the client repository remains the source of truth and
the state is loaded at startup. Writes (create collection/item, publish,
promote hero) arrive in phase 2 behind a per-tenant token, with the SQLite
store — until then a content change means a push and a restart.

Endpoints (spec §6.1; static equivalents in parentheses):

    GET /health                      liveness (ops; no envelope)
    GET /schema                      the card contract, verbatim (api/schema.json)
    GET /collections                 envelope: collections (api/collections.json)
    GET /collections/{id}/items      envelope: the collection's items
    GET /items/{asset_id}            envelope: one full record (api/items/<id>.json)
    GET /search?q=...                envelope: matching slim records
    GET /assets/content/...          client assets of INCLUDED records only

Gating is identical to the build's (gate_content): a draft or an above-tier
record does not exist for this server — 404, and its assets are not served.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from . import CONTRACT_VERSION, __version__
from .api import _envelope, _tokenize, build_search_index
from .build import (
    BuildFailure,
    _is_url,
    check_config,
    gate_content,
    load_config,
    read_content,
)
from .log import BuildLogger
from .report import BuildReport

# Names that describe records, never assets — they must never be downloadable.
RESERVED_FILENAMES = {"card.json", "collection.json"}


@dataclass
class ServeState:
    """The gated museum this server publishes."""

    repo: Path
    museum_id: str
    generated: str
    tier: str
    collections: list[dict]
    items: list[dict]
    index: dict
    included_collections: set[str]
    included_items: set[tuple[str, str]]
    covers: dict[str, Path] = field(default_factory=dict)
    skin: dict[str, Path] = field(default_factory=dict)
    logger: BuildLogger | None = None


def load_state(repo: Path, *, entitlements_key: Path | None = None) -> ServeState:
    """Run the build's read + gate pipeline in memory (no emission)."""
    repo = Path(repo)
    config = load_config(repo)
    museum_cfg = config.get("museum") or {}
    report = BuildReport(
        museum_id=museum_cfg.get("id", "<unknown>"),
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
        entitled_tier=(config.get("entitlements") or {}).get("tier", "<unknown>"),
    )
    # Servers log every line to stderr and buffer nothing (long-running).
    logger = BuildLogger(report.museum_id, buffer=False, mirror=True)
    report._logger = logger

    entitlement = check_config(config, report, entitlements_key=entitlements_key)
    report.entitled_tier = entitlement["tier"]
    report.modules = entitlement["modules"]

    collections, items, _site = read_content(repo, report)
    if report.errors:
        raise BuildFailure(report)
    included_collections, included_items = gate_content(
        report, collections, items, entitlement["tier"]
    )

    generated = datetime.now(timezone.utc).date().isoformat()

    served_items: list[dict] = []
    for item in included_items:
        record = {k: v for k, v in item.items() if k != "_dir"}
        item_dir = item["_dir"]
        # Same path layout the static build emits, so views cannot tell the
        # difference between static and dynamic.
        base = f"assets/content/{item['colecao']}/{item['asset_id']}"
        for key in ("image", "model_primary"):
            value = record.get(key)
            if value and not _is_url(value) and (item_dir / value).is_file():
                record[key] = f"{base}/{value}"
        served_items.append(record)

    served_collections: list[dict] = []
    covers: dict[str, Path] = {}
    for collection in included_collections:
        entry = {k: v for k, v in collection.items() if k != "_dir" and v is not None}
        entry.pop("website_status", None)
        cover = entry.get("cover")
        if cover and not _is_url(cover):
            source = collection["_dir"] / cover
            if source.is_file():
                entry["cover"] = f"assets/content/{collection['id']}/{cover}"
                covers[collection["id"]] = source.resolve()
        served_collections.append(entry)

    skin: dict[str, Path] = {}
    for _slot, value in sorted(((config.get("site") or {}).get("skin") or {}).items()):
        if not _is_url(value):
            source = repo / value
            if source.is_file():
                skin[Path(value).name] = source.resolve()

    state = ServeState(
        repo=repo,
        museum_id=report.museum_id,
        generated=generated,
        tier=entitlement["tier"],
        collections=served_collections,
        items=served_items,
        index=build_search_index(served_items),
        included_collections={c["id"] for c in served_collections},
        included_items={(i["colecao"], i["asset_id"]) for i in served_items},
        covers=covers,
        skin=skin,
        logger=logger,
    )
    logger.log(
        "serve_start",
        repo=str(repo),
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
        collections=len(served_collections),
        items=len(served_items),
    )
    return state


def create_app(repo: Path, *, entitlements_key: Path | None = None) -> FastAPI:
    """Build the FastAPI app for one client repository (one tenant)."""
    state = load_state(repo, entitlements_key=entitlements_key)
    app = FastAPI(title=f"MUSA collection API — {state.museum_id}", version=__version__)
    app.state.serve = state

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        t0 = time.monotonic()
        response = await call_next(request)
        state.logger.log(
            "api_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=int((time.monotonic() - t0) * 1000),
        )
        return response

    def envelope(data, count: int | None = None):
        return _envelope(data, museum_id=state.museum_id, generated=state.generated, count=count)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "museum": state.museum_id,
            "version": __version__,
            "contract": CONTRACT_VERSION,
        }

    @app.get("/schema")
    def schema():
        import json

        schema_src = Path(__file__).parent / "schemas" / "card.schema.json"
        return json.loads(schema_src.read_text(encoding="utf-8"))

    @app.get("/collections")
    def list_collections():
        return envelope(state.collections, count=len(state.collections))

    @app.get("/collections/{collection_id}/items")
    def list_items(collection_id: str):
        if collection_id not in state.included_collections:
            # Same rule as the static API: an excluded collection does not exist.
            raise HTTPException(status_code=404, detail="collection not found")
        items = [i for i in state.items if i.get("colecao") == collection_id]
        return envelope(items, count=len(items))

    @app.get("/items/{asset_id}")
    def get_item(asset_id: str):
        for item in state.items:
            if item["asset_id"] == asset_id:
                return envelope(item)
        raise HTTPException(status_code=404, detail="item not found")

    @app.get("/search")
    def search(q: str = ""):
        tokens = _tokenize(q)
        if not tokens:
            return envelope([], count=0)
        ids: set[str] | None = None
        for token in tokens:
            bucket = set(state.index["terms"].get(token, []))
            ids = bucket if ids is None else ids & bucket
        hits = [state.index["items"][i] for i in sorted(ids or [])]
        return envelope(hits, count=len(hits))

    @app.get("/assets/content/{collection}/{rest:path}")
    def asset(collection: str, rest: str):
        # Skin files live at the repository root; everything else under content/.
        if collection == "_skin":
            target = state.skin.get(rest)
            if target and target.is_file():
                return FileResponse(target)
            raise HTTPException(status_code=404, detail="asset not found")

        if collection not in state.included_collections:
            raise HTTPException(status_code=404, detail="asset not found")
        base = (state.repo / "content" / collection).resolve()
        target = (base / rest).resolve()
        try:
            relative = target.relative_to(base)
        except ValueError:
            raise HTTPException(status_code=404, detail="asset not found")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="asset not found")
        # Dotfiles and record descriptors are never downloadable assets.
        if any(part.startswith(".") for part in relative.parts):
            raise HTTPException(status_code=404, detail="asset not found")
        if target.name in RESERVED_FILENAMES:
            raise HTTPException(status_code=404, detail="asset not found")
        # Allowed: the collection's cover, or a file inside an included item's dir.
        if target == state.covers.get(collection):
            return FileResponse(target)
        first = relative.parts[0]
        if (collection, first) in state.included_items and len(relative.parts) > 1:
            return FileResponse(target)
        raise HTTPException(status_code=404, detail="asset not found")

    return app

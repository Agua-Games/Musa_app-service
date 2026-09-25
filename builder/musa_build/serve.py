"""Dynamic collection API (ADR 0008, phase M1.4): ``musa-build serve``.

Same shapes, envelope and gating as the static API (api.py) — the frontend's
``live`` mode talks to this server exactly as it talks to the emitted JSON
files, so switching static <-> dynamic is a ``baseUrl`` change, never a view
change (see source/assets/js/api.js).

Reads (spec §6.1; static equivalents in parentheses):

    GET /health                      liveness (ops; no envelope)
    GET /schema                      the card contract, verbatim (api/schema.json)
    GET /collections                 envelope: collections (api/collections.json)
    GET /collections/{id}/items      envelope: the collection's items
    GET /items/{asset_id}            envelope: one full record (api/items/<id>.json)
    GET /search?q=...                envelope: matching slim records
    GET /assets/content/...          client assets of INCLUDED records only

Writes (M1.4 phase 2) — all behind the per-tenant bearer token
(``MUSA_ADMIN_TOKEN`` env on the server; without it the instance is
read-only and writes answer 503):

    POST /auth/login                 {email, password: <tenant token>} -> {token, user}
    POST /items                      patch an existing card ({asset_id, ...fields})
                                     or create a new one (full card; status
                                     defaults to draft — fail closed)
    POST /collections                {id, title, description?, tier?}

Persistence: the repository stays the seed; edits land in a SQLite overlay
(``store.py``) applied on top of the seed at startup. Gating is the build's
own code (gate_content): a draft or above-tier record is a 404 and its assets
are not served. A valid admin token additionally sees the tenant's DRAFTS
(tier gating still applies — fail closed on entitlements, always).
"""

import hmac
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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
from .contract import make_validator, validate_card
from .gate import gate_status, gate_tier
from .log import BuildLogger
from .report import BuildReport
from .store import Store

# Names that describe records, never assets — they must never be downloadable.
RESERVED_FILENAMES = {"card.json", "collection.json"}

# Folder-style ids: lowercase slug, the same rule the repository layout implies.
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass
class ServeState:
    """The museum this server publishes: seed + overlay, gated views derived."""

    repo: Path
    museum_id: str
    generated: str
    tier: str
    store: Store | None
    all_collections: list[dict]  # seed + overlay, ungated
    all_items: list[dict]        # seed + overlay, ungated
    collections: list[dict] = field(default_factory=list)   # public (gated)
    items: list[dict] = field(default_factory=list)         # public (gated)
    admin_items: list[dict] = field(default_factory=list)   # published + drafts, tier-gated
    index: dict = field(default_factory=dict)
    included_collections: set[str] = field(default_factory=set)
    included_items: set[tuple[str, str]] = field(default_factory=set)
    covers: dict[str, Path] = field(default_factory=dict)
    skin: dict[str, Path] = field(default_factory=dict)
    logger: BuildLogger | None = None


# ---------------------------------------------------------------- state ----

def _shape_item(item: dict) -> dict:
    """The public record: assets point at the same paths the static build emits."""
    record = {k: v for k, v in item.items() if k != "_dir"}
    item_dir = item.get("_dir")
    if item_dir is not None:
        base = f"assets/content/{item['colecao']}/{item['asset_id']}"
        for key in ("image", "model_primary"):
            value = record.get(key)
            if value and not _is_url(value) and (item_dir / value).is_file():
                record[key] = f"{base}/{value}"
    return record


def _shape_collection(collection: dict, covers: dict[str, Path]) -> dict:
    entry = {k: v for k, v in collection.items() if k != "_dir" and v is not None}
    entry.pop("website_status", None)
    cover = entry.get("cover")
    if cover and not _is_url(cover) and collection.get("_dir") is not None:
        source = collection["_dir"] / cover
        if source.is_file():
            entry["cover"] = f"assets/content/{collection['id']}/{cover}"
            covers[collection["id"]] = source.resolve()
    return entry


def _regate(state: ServeState) -> None:
    """Recompute the public and admin views from all_* with the build's gate."""
    report = BuildReport(
        museum_id=state.museum_id,
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
        entitled_tier=state.tier,
    )
    report._logger = state.logger  # server-mode logger (stderr, no buffer)
    included_collections, included_items = gate_content(
        report, state.all_collections, state.all_items, state.tier
    )

    state.covers = {}
    state.collections = [_shape_collection(c, state.covers) for c in included_collections]
    state.items = [_shape_item(i) for i in included_items]
    state.index = build_search_index(state.items)
    state.included_collections = {c["id"] for c in included_collections}
    state.included_items = {(i["colecao"], i["asset_id"]) for i in included_items}

    # The admin view adds the tenant's own drafts (status-gated only). Tier
    # gating never relaxes: an above-entitlement record stays invisible.
    included_collection_ids = state.included_collections
    state.admin_items = [
        _shape_item(i)
        for i in state.all_items
        if i.get("colecao") in included_collection_ids
        and gate_tier(i.get("tier"), state.tier).included
    ]


def load_state(repo: Path, *, data_dir: Path | None = None,
               entitlements_key: Path | None = None, store: Store | None = None) -> ServeState:
    """Load the seed repository, apply the SQLite overlay, gate everything."""
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

    if store is None:
        store = Store(Path(data_dir) if data_dir else repo / ".musa")

    # The overlay wins over the seed; overlay-only records are additions.
    seed_collections = {c["id"]: c for c in collections}
    for meta in store.load_collections():
        overlay = dict(meta)
        overlay["_dir"] = None
        seed_collections[meta["id"]] = overlay
    all_collections = list(seed_collections.values())

    seed_items = {(i["colecao"], i["asset_id"]): i for i in items}
    for card in store.load_items():
        card = dict(card)
        card["_dir"] = None
        seed_items[(card["colecao"], card["asset_id"])] = card
    all_items = list(seed_items.values())

    skin: dict[str, Path] = {}
    for _slot, value in sorted(((config.get("site") or {}).get("skin") or {}).items()):
        if not _is_url(value):
            source = repo / value
            if source.is_file():
                skin[Path(value).name] = source.resolve()

    state = ServeState(
        repo=repo,
        museum_id=report.museum_id,
        generated=datetime.now(timezone.utc).date().isoformat(),
        tier=entitlement["tier"],
        store=store,
        all_collections=all_collections,
        all_items=all_items,
        skin=skin,
        logger=logger,
    )
    _regate(state)
    logger.log(
        "serve_start",
        repo=str(repo),
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
        collections=len(state.collections),
        items=len(state.items),
        overlay_items=len(store.load_items()),
        overlay_collections=len(store.load_collections()),
    )
    return state


# ------------------------------------------------------------------ app ----

def create_app(repo: Path, *, data_dir: Path | None = None,
               entitlements_key: Path | None = None) -> FastAPI:
    """Build the FastAPI app for one client repository (one tenant)."""
    state = load_state(repo, data_dir=data_dir, entitlements_key=entitlements_key)
    app = FastAPI(title=f"MUSA collection API — {state.museum_id}", version=__version__)
    app.state.serve = state

    # The client site (static hosting) calls the API cross-origin. Bearer-token
    # writes stay safe with "*" because no cookies/credentials are involved;
    # tightening to the tenant domain is a deployment-time refinement.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- auth (per-tenant bearer token) -----------------------------------
    def configured_token() -> str | None:
        return os.environ.get("MUSA_ADMIN_TOKEN") or None

    def is_admin(request: Request) -> bool:
        token = configured_token()
        if not token:
            return False
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return False
        return hmac.compare_digest(auth[7:].strip(), token)

    def require_admin(request: Request) -> None:
        if not configured_token():
            raise HTTPException(
                status_code=503,
                detail="writes disabled: the instance has no MUSA_ADMIN_TOKEN configured",
            )
        if not is_admin(request):
            raise HTTPException(status_code=401, detail="a valid bearer token is required")

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

    # ---- ops ---------------------------------------------------------------
    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "museum": state.museum_id,
            "version": __version__,
            "contract": CONTRACT_VERSION,
            "writes": "enabled" if configured_token() else "disabled",
        }

    @app.get("/schema")
    def schema():
        schema_src = Path(__file__).parent / "schemas" / "card.schema.json"
        return json.loads(schema_src.read_text(encoding="utf-8"))

    # ---- reads ---------------------------------------------------------------
    @app.get("/collections")
    def list_collections():
        return envelope(state.collections, count=len(state.collections))

    @app.get("/collections/{collection_id}/items")
    def list_items(collection_id: str, request: Request, include_drafts: bool = False):
        if collection_id not in state.included_collections:
            # Same rule as the static API: an excluded collection does not exist.
            raise HTTPException(status_code=404, detail="collection not found")
        source = state.items
        if include_drafts:
            require_admin(request)
            source = state.admin_items
        items = [i for i in source if i.get("colecao") == collection_id]
        return envelope(items, count=len(items))

    @app.get("/items/{asset_id}")
    def get_item(asset_id: str, request: Request):
        for item in state.items:
            if item["asset_id"] == asset_id:
                return envelope(item)
        if is_admin(request):
            for item in state.admin_items:
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

    # ---- writes (token required) ----------------------------------------------
    @app.post("/auth/login", status_code=200)
    def login(body: dict):
        # M1.4: one token per tenant; the password field carries it. Real
        # accounts (roles, SSO) arrive with the backend-of-scale (ADR 0008).
        if not configured_token():
            raise HTTPException(status_code=503, detail="this instance has no MUSA_ADMIN_TOKEN configured")
        if not hmac.compare_digest(str(body.get("password") or ""), configured_token()):
            raise HTTPException(status_code=401, detail="invalid credentials")
        email = str(body.get("email") or "curator")
        state.logger.log("auth_login", email=email)
        return {
            "token": configured_token(),
            "user": {
                "email": email,
                "name": email.split("@")[0].replace(".", " ").title(),
                "role": "client",
                "org": state.museum_id,
                "note": "Tenant admin token session",
            },
        }

    @app.post("/collections", status_code=201)
    def create_collection(body: dict, request: Request):
        require_admin(request)
        collection_id = str(body.get("id") or "")
        if not ID_PATTERN.match(collection_id):
            raise HTTPException(status_code=422, detail="id must be a lowercase slug (a-z, 0-9, -)")
        if any(c["id"] == collection_id for c in state.all_collections):
            raise HTTPException(status_code=409, detail=f"collection {collection_id!r} already exists")
        meta = {
            "id": collection_id,
            "title": str(body.get("title") or collection_id),
            "description": str(body.get("description") or ""),
            "tier": body.get("tier"),
            "subcollections": [],
            "website_status": body.get("website_status") or "published",
            "_dir": None,
        }
        state.store.upsert_collection({k: v for k, v in meta.items() if k != "_dir"})
        state.all_collections.append(meta)
        _regate(state)
        state.logger.log("api_write", action="create_collection", asset=collection_id)
        if collection_id not in state.included_collections:
            # Created but gated out (e.g. a draft) — say so explicitly.
            return envelope({"id": collection_id, "visible": False,
                             "detail": "created as non-published; visible to admins only"})
        created = next(c for c in state.collections if c["id"] == collection_id)
        return envelope(created)

    @app.post("/items", status_code=200)
    def save_item(body: dict, request: Request):
        """Patch an existing card ({asset_id, ...fields}) or create a new one
        (full card). New cards default to draft — publishing is a separate,
        explicit patch."""
        require_admin(request)
        asset_id = str(body.get("asset_id") or "")
        if not ID_PATTERN.match(asset_id):
            raise HTTPException(status_code=422, detail="asset_id must be a lowercase slug (a-z, 0-9, -)")

        existing = next((i for i in state.all_items if i.get("asset_id") == asset_id), None)
        if existing is not None:
            card = {k: v for k, v in existing.items() if k != "_dir"}
            card.update(body)
            card["asset_id"] = asset_id
            card["colecao"] = existing["colecao"]  # the folder rule: never moves via patch
        else:
            card = dict(body)
            card.setdefault("website_status", "draft")  # fail closed
            collection = card.get("colecao")
            if not any(c["id"] == collection for c in state.all_collections):
                raise HTTPException(status_code=422, detail=f"unknown collection {collection!r}")

        validator = make_validator()
        problems = validate_card(card, validator)
        if problems:
            raise HTTPException(status_code=422, detail="; ".join(problems))

        state.store.upsert_item(card)
        card["_dir"] = existing.get("_dir") if existing else None
        if existing is not None:
            state.all_items[state.all_items.index(existing)] = card
        else:
            state.all_items.append(card)
        _regate(state)
        state.logger.log(
            "api_write",
            action="patch_item" if existing else "create_item",
            asset=asset_id,
            visible=any(i["asset_id"] == asset_id for i in state.items),
        )
        shaped = _shape_item(card)
        return envelope(shaped)

    # ---- assets (gated, read-only) --------------------------------------------
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

"""Build orchestration: client repository -> static site.

Input (the client repository):
    museum.config.json      identity, pinned MUSA version, entitlements
    content/<collection>/collection.json        (optional) title, cover, tier...
    content/<collection>/<item>/card.json      the contract record + presentation fields
    content/<collection>/<item>/<assets...>     images, models (or URLs in the card)
    content/site.json                           (optional) films, products, wallHotspots

Output (the published site):
    <frontend files, minus demo content and dev-server files>
    data/catalog.js / data/catalog.json         generated payload (gated)
    assets/content/...                          copied client assets (included items only)
    build-report.json / build-report.md         what went in, what stayed out, why
    build-log.jsonl                             every decision as a JSON line (M1.5)
"""

import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from . import CONTRACT_VERSION, __version__
from .api import emit_api
from .contract import make_validator, validate_card
from .entitlements import load_public_key, verify_entitlements
from .gate import check_tier, gate_record, gate_tier
from .log import get_logger
from .report import BuildReport, Entry

# The frontend folder doubles as the platform's own published demo, so the
# builder copies only the platform code and regenerates the content layer.
# Demo imagery, demo models and the dev server never reach a client build.
FRONTEND_EXCLUDE_DIRS = {"data", "assets/img", "assets/models", "assets/video"}
FRONTEND_EXCLUDE_FILES = {"server.mjs", "package.json", "README.md"}

CONTENT_ASSETS_PREFIX = "assets/content"


class BuildFailure(Exception):
    """The build failed; ``report`` carries the reasons and is still written."""

    def __init__(self, report: BuildReport):
        super().__init__("; ".join(report.errors) or "build failed")
        self.report = report


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "//"))


def load_config(repo: Path) -> dict:
    config_path = repo / "museum.config.json"
    if not config_path.is_file():
        raise BuildFailure(_orphan_report(f"museum.config.json not found in {repo}"))
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildFailure(_orphan_report(f"museum.config.json is not valid JSON: {exc}"))
    return config


def _orphan_report(error: str) -> BuildReport:
    report = BuildReport(
        museum_id="<unknown>",
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
        entitled_tier="<unknown>",
    )
    report.fail(error)
    return report


def check_config(config: dict, report: BuildReport, *, entitlements_key: Path | None = None) -> dict:
    """Validate museum.config.json; returns the normalized entitlement view."""
    errors = []
    museum = config.get("museum") or {}
    for key in ("id", "name"):
        if not museum.get(key):
            errors.append(f"museum.config.json: museum.{key} is required")
    entitlements = config.get("entitlements") or {}
    tier = (entitlements.get("tier") or "").lower()
    try:
        check_tier(tier)
    except ValueError as exc:
        errors.append(f"museum.config.json: {exc}")

    pin = config.get("musa")
    if not pin:
        errors.append("museum.config.json: 'musa' must pin the artifact version")
    elif pin not in (__version__, "0.0.0-unreleased"):
        errors.append(
            f"museum.config.json pins musa {pin!r} but this builder is {__version__} — "
            "run the container image with the pinned tag (version upgrades are a one-line change)"
        )

    if errors:
        for error in errors:
            report.fail(error)
        raise BuildFailure(report)

    # Signed entitlements (ADR 0010): release builds must verify the platform's
    # Ed25519 signature; the dev pin keeps local iteration unsigned.
    log = get_logger(report)
    if pin == "0.0.0-unreleased":
        if not entitlements.get("signature"):
            report.warn(
                "unsigned entitlements accepted because this is a development build "
                "(musa: 0.0.0-unreleased); release images require the platform's signature"
            )
        log.log("entitlements", mode="dev-unsigned" if not entitlements.get("signature") else "dev-signed")
    else:
        signature_errors = verify_entitlements(config, load_public_key(entitlements_key))
        if signature_errors:
            for error in signature_errors:
                report.fail(f"museum.config.json: {error}")
            raise BuildFailure(report)
        log.log("entitlements", mode="signed", expires=entitlements.get("expires"))

    log.log("config_validated", tier=tier, modules=list(entitlements.get("modules") or []))
    return {
        "tier": tier,
        "modules": list(entitlements.get("modules") or []),
    }


def copy_frontend(frontend: Path, out: Path) -> int:
    """Copy the platform code, excluding the demo content and dev-server files."""
    copied = 0
    for path in sorted(frontend.rglob("*")):
        rel = path.relative_to(frontend).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in FRONTEND_EXCLUDE_DIRS):
            continue
        if rel in FRONTEND_EXCLUDE_FILES:
            continue
        target = out / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied += 1
    return copied


def _copy_asset(repo: Path, rel_path: str, target_rel: str, out: Path, report: BuildReport, owner: str) -> str:
    """Copy one client asset into the payload, returning the site-relative path."""
    source = repo / rel_path
    if not source.is_file():
        report.warn(f"{owner}: referenced asset {rel_path!r} not found — left as-is")
        return rel_path
    target = out / target_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    get_logger(report).log("asset_write", asset=owner, path=target_rel, bytes=source.stat().st_size)
    return target_rel


def _rewrite_item_assets(repo: Path, item_dir: Path, item: dict, out: Path, report: BuildReport) -> dict:
    """Copy an included item's assets and point its fields at the emitted paths."""
    collection_id = item["colecao"]
    asset_id = item["asset_id"]
    base = f"{CONTENT_ASSETS_PREFIX}/{collection_id}/{asset_id}"

    for path in sorted(item_dir.rglob("*")):
        if path.is_dir() or path.name == "card.json" or path.name.startswith("."):
            continue
        rel_in_item = path.relative_to(item_dir).as_posix()
        _copy_asset(repo, path.relative_to(repo).as_posix(), f"{base}/{rel_in_item}", out, report, asset_id)

    item = dict(item)
    for key in ("image", "model_primary"):
        value = item.get(key)
        if value and not _is_url(value) and (item_dir / value).is_file():
            item[key] = f"{base}/{value}"
    return item


def read_content(repo: Path, report: BuildReport) -> tuple[list[dict], list[dict], dict]:
    """Walk content/ into (collections, items, site sections). NO gating here."""
    content = repo / "content"
    collections: list[dict] = []
    items: list[dict] = []
    site: dict = {}

    site_file = content / "site.json"
    if site_file.is_file():
        site = json.loads(site_file.read_text(encoding="utf-8"))

    if not content.is_dir():
        report.warn("no content/ directory — building an empty museum")
        return collections, items, site

    validator = make_validator()
    for collection_dir in sorted(p for p in content.iterdir() if p.is_dir()):
        collection_id = collection_dir.name
        meta_file = collection_dir / "collection.json"
        meta = {}
        if meta_file.is_file():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                report.fail(f"{collection_id}/collection.json is not valid JSON: {exc}")
                continue
        collections.append(
            {
                "id": collection_id,
                "title": meta.get("title", collection_id),
                "description": meta.get("description", ""),
                "cover": meta.get("cover"),
                "tier": meta.get("tier"),
                "subcollections": meta.get("subcollections", []),
                "website_status": meta.get("website_status", "published"),
                "_dir": collection_dir,
            }
        )
        for item_dir in sorted(p for p in collection_dir.iterdir() if p.is_dir()):
            card_path = item_dir / "card.json"
            if not card_path.is_file():
                report.warn(f"{collection_id}/{item_dir.name}: no card.json — skipped")
                continue
            try:
                card = json.loads(card_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                report.fail(f"{collection_id}/{item_dir.name}/card.json is not valid JSON: {exc}")
                continue
            problems = validate_card(card, validator)
            for problem in problems:
                report.fail(f"{card.get('asset_id', item_dir.name)}: {problem}")
            # Folder identity IS the record identity (see the contract field docs).
            if card.get("colecao") and card["colecao"] != collection_id:
                report.fail(
                    f"{card.get('asset_id', item_dir.name)}: colecao is {card['colecao']!r} "
                    f"but the folder is {collection_id!r}"
                )
            if card.get("asset_id") and card["asset_id"] != item_dir.name:
                report.fail(
                    f"{card['asset_id']}: asset_id must equal the item folder name {item_dir.name!r}"
                )
            card["_dir"] = item_dir
            items.append(card)

    return collections, items, site


def build_site(repo: Path, frontend: Path, out: Path, *, entitlements_key: Path | None = None) -> BuildReport:
    repo = Path(repo)
    out = Path(out)
    config = load_config(repo)
    museum_cfg = config.get("museum") or {}
    report = BuildReport(
        museum_id=museum_cfg.get("id", "<unknown>"),
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
        entitled_tier=(config.get("entitlements") or {}).get("tier", "<unknown>"),
    )
    log = get_logger(report)
    report.build_id = log.build_id
    t0 = time.monotonic()
    log.log(
        "build_start",
        repo=str(repo),
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
    )
    entitlement = check_config(config, report, entitlements_key=entitlements_key)
    report.entitled_tier = entitlement["tier"]
    report.modules = entitlement["modules"]

    collections, items, site = read_content(repo, report)
    if report.errors:
        raise BuildFailure(report)
    log.log(
        "content_read",
        collections=len(collections),
        items=len(items),
        site_sections=sorted(site.keys()),
    )

    # Gate collections first; items of an excluded collection are excluded too.
    included_collections: list[dict] = []
    excluded_collections: dict[str, str] = {}
    for collection in collections:
        decision = gate_record(collection, entitlement["tier"])
        report.entries.append(Entry("collection", collection["id"], decision.included, decision.reasons))
        log.log("gate", asset=collection["id"], kind="collection",
                included=decision.included, reasons=decision.reasons)
        if decision.included:
            included_collections.append(collection)
        else:
            excluded_collections[collection["id"]] = "; ".join(decision.reasons)

    included_items: list[dict] = []
    for item in items:
        asset_id = item.get("asset_id", "?")
        if item.get("colecao") in excluded_collections:
            reason = f"collection {item['colecao']!r} excluded: {excluded_collections[item['colecao']]}"
            report.entries.append(Entry("item", asset_id, False, [reason]))
            log.log("gate", asset=asset_id, kind="item", included=False, reasons=[reason])
            continue
        decision = gate_record(item, entitlement["tier"])
        report.entries.append(Entry("item", asset_id, decision.included, decision.reasons))
        log.log("gate", asset=asset_id, kind="item",
                included=decision.included, reasons=decision.reasons)
        if decision.included:
            included_items.append(item)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    frontend_files = copy_frontend(Path(frontend), out)
    log.log("frontend_copied", files=frontend_files)

    # Only INCLUDED records contribute bytes to the payload (invariant 5.2).
    emitted_items = [
        _rewrite_item_assets(repo, item["_dir"], item, out, report) for item in included_items
    ]
    for item in emitted_items:
        item.pop("_dir", None)

    emitted_collections = []
    for collection in included_collections:
        entry = {k: v for k, v in collection.items() if k != "_dir" and v is not None}
        cover = entry.get("cover")
        if cover and not _is_url(cover):
            source = collection["_dir"] / cover
            if source.is_file():
                entry["cover"] = _copy_asset(
                    repo,
                    source.relative_to(repo).as_posix(),
                    f"{CONTENT_ASSETS_PREFIX}/{collection['id']}/{cover}",
                    out,
                    report,
                    collection["id"],
                )
            else:
                report.warn(f"{collection['id']}: cover {cover!r} not found — left as-is")
        entry.pop("website_status", None)
        emitted_collections.append(entry)

    skin = ((config.get("site") or {}).get("skin")) or {}
    emitted_skin = {}
    for slot, value in sorted(skin.items()):
        if _is_url(value):
            emitted_skin[slot] = value
        else:
            emitted_skin[slot] = _copy_asset(
                repo, value, f"{CONTENT_ASSETS_PREFIX}/_skin/{Path(value).name}", out, report, f"skin.{slot}"
            )

    plans = json.loads((Path(__file__).parent / "data" / "plans.json").read_text(encoding="utf-8"))
    site_cfg = config.get("site") or {}
    catalog = {
        "generated": datetime.now(timezone.utc).date().isoformat(),
        "contract": "schemas/card/v1/card.schema.json",
        "museum": {
            "id": museum_cfg["id"],
            "name": museum_cfg["name"],
            "tagline": museum_cfg.get("tagline", ""),
            "tier": entitlement["tier"],
            "locale": museum_cfg.get("locale", "pt-BR"),
            "domain": museum_cfg.get("domain", ""),
            "modules": entitlement["modules"],
            "heroVideo": site_cfg.get("heroVideo"),
            "skin": emitted_skin,
        },
        "collections": emitted_collections,
        "items": emitted_items,
        "salon": site.get("salon", []),
        "films": site.get("films", []),
        "products": site.get("products", []),
        "plans": plans,
        "wallHotspots": site.get("wallHotspots", []),
        "accounts": [],
    }

    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    payload = json.dumps(catalog, ensure_ascii=False, indent=2)
    (data_dir / "catalog.json").write_text(payload + "\n", encoding="utf-8")
    log.log("file_emitted", path="data/catalog.json", bytes=len(payload))
    (data_dir / "catalog.js").write_text(
        "/**\n"
        " * MUSA — generated catalog. Do not edit: this file is a build artifact.\n"
        f" * Generated by musa-app {__version__} (contract v{CONTRACT_VERSION}) from the\n"
        " * client repository's content/. Edit the cards and rebuild instead.\n"
        " */\n"
        f"window.MUSA_MOCK = {payload};\n",
        encoding="utf-8",
    )
    log.log("file_emitted", path="data/catalog.js")

    # The static collection API (ADR 0008, M1.1): same shapes the dynamic
    # backend will serve — already gated, so a draft is not even a file.
    generated = catalog["generated"]
    emit_api(
        out,
        museum_id=museum_cfg["id"],
        generated=generated,
        collections=emitted_collections,
        items=emitted_items,
        logger=log,
    )

    # Runtime boot config: client sites read the collection data through the
    # static API (live mode); the platform demo keeps the in-browser mock.
    (data_dir / "runtime.js").write_text(
        "/**\n"
        " * MUSA — generated runtime config. Do not edit: this file is a build artifact.\n"
        " * The static API is read-only; writes arrive with the M1.4 backend.\n"
        " */\n"
        'window.MUSA_RUNTIME = { mode: "live", baseUrl: "api", static: true };\n',
        encoding="utf-8",
    )
    log.log("file_emitted", path="data/runtime.js")

    # The report's API view (M1.5): each decision says WHERE the record landed.
    # Excluded records keep an empty list — "not emitted anywhere" is the answer.
    entries_by_ref = {(e.kind, e.ref): e for e in report.entries}
    for collection in emitted_collections:
        entry = entries_by_ref.get(("collection", collection["id"]))
        if entry:
            entry.artifacts = ["data/catalog.json", "api/collections.json",
                               f"api/collections/{collection['id']}/items.json"]
    for item in emitted_items:
        entry = entries_by_ref.get(("item", item["asset_id"]))
        if entry:
            entry.artifacts = ["data/catalog.json", f"api/items/{item['asset_id']}.json",
                               f"api/collections/{item['colecao']}/items.json", "api/search.json"]

    log.log(
        "build_end",
        result="success" if report.ok else "failure",
        duration_ms=int((time.monotonic() - t0) * 1000),
        **report.counts(),
    )
    report.write(out)
    return report

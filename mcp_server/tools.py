"""The MUSA collection tools (M1.6). Pure functions over a client repository —
the MCP protocol wrapper lives in server.py; everything here is unit-testable.

Data comes from the repository itself (the seed is the source of truth until
the M1.4 backend exists), reusing the builder's own machinery — read_content,
the contract validator, the gate and the search index — so the MCP can never
disagree with the build.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "builder"))

from musa_build.build import BuildFailure, build_site, read_content  # noqa: E402
from musa_build.contract import make_validator, validate_card  # noqa: E402
from musa_build.gate import gate_record  # noqa: E402
from musa_build.report import BuildReport  # noqa: E402
from musa_build import CONTRACT_VERSION, __version__ as BUILDER_VERSION  # noqa: E402
from musa_build.api import build_search_index  # noqa: E402

ITEM_STATUSES = ("draft", "published")


class MusaRepo:
    """A client repository opened for MCP operations."""

    def __init__(self, repo: Path):
        self.repo = Path(repo)
        if not (self.repo / "museum.config.json").is_file():
            raise ValueError(f"{self.repo} is not a MUSA client repository (no museum.config.json)")

    def _report(self) -> BuildReport:
        config = json.loads((self.repo / "museum.config.json").read_text(encoding="utf-8"))
        museum = config.get("museum") or {}
        return BuildReport(
            museum_id=museum.get("id", "<unknown>"),
            builder_version=BUILDER_VERSION,
            contract_version=CONTRACT_VERSION,
            entitled_tier=(config.get("entitlements") or {}).get("tier", "<unknown>"),
        )

    def read(self) -> tuple[list[dict], list[dict], dict, BuildReport]:
        report = self._report()
        collections, items, site = read_content(self.repo, report)
        return collections, items, site, report

    def tier(self) -> str:
        config = json.loads((self.repo / "museum.config.json").read_text(encoding="utf-8"))
        return ((config.get("entitlements") or {}).get("tier") or "bronze").lower()

    def item_dir(self, asset_id: str) -> Path | None:
        for card_path in self.repo.glob("content/*/*/card.json"):
            if card_path.parent.name == asset_id:
                return card_path.parent
        return None


def _src(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


# --------------------------------------------------------------------- tools

def list_collections(repo: MusaRepo) -> dict:
    collections, items, _, report = repo.read()
    entitled = repo.tier()
    out = []
    for c in collections:
        decision = gate_record(c, entitled)
        out.append({
            "id": c["id"],
            "title": c["title"],
            "tier": c.get("tier") or "bronze",
            "published": decision.included,
            "items": sum(1 for i in items if i.get("colecao") == c["id"]),
            "reasons": decision.reasons,
            "source": _src(c["_dir"] / "collection.json", repo.repo),
        })
    result = {"museum": report.museum_id, "entitled_tier": entitled, "collections": out}
    if report.errors:
        result["content_errors"] = report.errors
    return result


def get_item(repo: MusaRepo, asset_id: str) -> dict:
    _, items, _, _ = repo.read()
    item = next((i for i in items if i.get("asset_id") == asset_id), None)
    if item is None:
        return {"error": f"item {asset_id!r} not found",
                "hint": "use list_collections to see what exists"}
    decision = gate_record(item, repo.tier())
    card_path = _src(item["_dir"] / "card.json", repo.repo)
    record = {k: v for k, v in item.items() if not k.startswith("_")}
    return {
        "item": record,
        "published": decision.included,
        "reasons": decision.reasons,
        "sources": [card_path, f"asset_id:{asset_id}"],
    }


def search(repo: MusaRepo, query: str) -> dict:
    """Token search over the collection — every hit is traceable to an asset_id."""
    _, items, _, _ = repo.read()
    index = build_search_index(items)
    tokens = [t for t in query.lower().split() if len(t) >= 2]
    ids: set[str] | None = None
    for token in tokens:
        bucket = set()
        for term, term_ids in index["terms"].items():
            if token in term:
                bucket.update(term_ids)
        ids = bucket if ids is None else ids & bucket
    hits = []
    for asset_id in sorted(ids or []):
        summary = index["items"][asset_id]
        hits.append({
            **summary,
            "sources": [f"asset_id:{asset_id}",
                        f"content/{summary['colecao']}/{asset_id}/card.json"],
        })
    return {"query": query, "count": len(hits), "results": hits}


def validate_card_tool(repo: MusaRepo, card: dict) -> dict:
    validator = make_validator()
    problems = validate_card(card, validator)
    return {
        "valid": not problems,
        "problems": problems,
        "contract": f"schemas/card/v{CONTRACT_VERSION}/card.schema.json",
        "sources": ["schemas/card.schema.json"],
    }


def propose_card_correction(repo: MusaRepo, card: dict, folder: str | None = None,
                             collection: str | None = None) -> dict:
    """Propose — never silently apply — fixes for a card outside the contract."""
    corrected = dict(card)
    changes: list[str] = []

    # Mechanical identity fixes: the folder IS the identity (contract field docs).
    if folder and corrected.get("asset_id") != folder:
        changes.append(f"asset_id: {corrected.get('asset_id')!r} -> {folder!r} (folder identity rule)")
        corrected["asset_id"] = folder
    if collection and corrected.get("colecao") != collection:
        changes.append(f"colecao: {corrected.get('colecao')!r} -> {collection!r} (folder identity rule)")
        corrected["colecao"] = collection

    if "website_status" not in corrected:
        corrected["website_status"] = "draft"
        changes.append("website_status: set to 'draft' (safe default — publish explicitly)")

    if "tags" in corrected and not isinstance(corrected["tags"], list):
        corrected["tags"] = [str(corrected["tags"])]
        changes.append("tags: wrapped into a list")

    remaining = validate_card(corrected, make_validator())
    # Missing required content fields are not invented — they are flagged.
    for problem in remaining:
        changes.append(f"NEEDS HUMAN INPUT: {problem}")

    return {
        "corrected": corrected,
        "changes": changes,
        "valid_after": not remaining,
        "note": "nothing was written — apply the corrected card to the repo and rebuild",
        "sources": ["schemas/card.schema.json"],
    }


def set_status(repo: MusaRepo, asset_id: str, status: str) -> dict:
    if status not in ITEM_STATUSES:
        return {"error": f"status must be one of {ITEM_STATUSES}"}
    item_dir = repo.item_dir(asset_id)
    if item_dir is None:
        return {"error": f"item {asset_id!r} not found"}
    card_path = item_dir / "card.json"
    card = json.loads(card_path.read_text(encoding="utf-8"))
    old = card.get("website_status")
    if old == status:
        return {"asset_id": asset_id, "status": status, "changed": False,
                "sources": [_src(card_path, repo.repo)]}
    card["website_status"] = status
    card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "asset_id": asset_id,
        "status": status,
        "previous": old,
        "changed": True,
        "note": "the change reaches the site on the next build (the gate is in the build)",
        "sources": [_src(card_path, repo.repo), f"asset_id:{asset_id}"],
    }


def upload_asset(repo: MusaRepo, **_) -> dict:
    return {
        "error": "blocked on M1.3 (object storage)",
        "reason": "binary assets move to per-client buckets (ADR 0009: Cloudflare R2); "
                  "until then, place the file next to the card in content/ and reference it by name",
        "sources": ["docs/adr/0009-object-storage.md"],
    }


def build_report(repo: MusaRepo) -> dict:
    """Run the real build into a throwaway dir and return the full report."""
    with tempfile.TemporaryDirectory() as tmp:
        frontend = Path(__file__).resolve().parent.parent / "source"
        try:
            report = build_site(repo.repo, frontend, Path(tmp) / "site")
        except BuildFailure as failure:
            report = failure.report
        result = report.to_dict()
        result["sources"] = ["build-report.json", f"build_id:{report.build_id}"]
        return result

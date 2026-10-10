"""Invariant assertions checked after persona actions (M3.3, born with M3.1).

A False `ok` is a top-severity beta finding: the product leaked something it
must never leak (a draft, an above-tier record, an invalid card) or the build
broke. Every invariant has a sanity test that forces it to fail once — an
invariant that never fails in its own sanity test is not an invariant.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .client import ApiClient

TIER_ORDER = {"bronze": 1, "silver": 2, "gold": 3}


@dataclass
class InvariantResult:
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"nome": self.name, "ok": self.ok, "detalhe": self.detail}


def _all_items_with_auth(client: ApiClient) -> list[dict]:
    cols = client.collections(auth=True).body["data"]
    items: list[dict] = []
    for c in cols:
        res = client.collection_items(c["id"], include_drafts=True, auth=True)
        if res.ok:
            items.extend(res.body["data"])
    return items


def check_no_drafts_in_public(client: ApiClient) -> InvariantResult:
    """Every non-published record known to the admin must be a public 404."""
    name = "nada-draft-no-publico"
    drafts = [i for i in _all_items_with_auth(client)
              if i.get("website_status") != "published"]
    leaks = []
    for d in drafts:
        res = client.item(d["asset_id"])  # no token — the public path
        if res.status != 404:
            leaks.append(d["asset_id"])
    if leaks:
        return InvariantResult(name, False, f"drafts visible publicly: {leaks[:5]}")
    return InvariantResult(name, True, f"{len(drafts)} draft(s) checked, all 404 publicly")


def check_tier_gate(client: ApiClient, museum_tier: str) -> InvariantResult:
    """Nothing above the museum's entitlement tier is served publicly."""
    name = "nada-acima-do-tier"
    allowed = TIER_ORDER[(museum_tier or "bronze").lower()]
    over = []
    for c in client.collections().body["data"]:
        if TIER_ORDER.get((c.get("tier") or "bronze").lower(), 99) > allowed:
            over.append(c["id"])
    items = _all_items_with_auth(client)
    leaks = []
    for i in items:
        rank = TIER_ORDER.get((i.get("tier") or "bronze").lower(), 99)
        if rank > allowed:
            res = client.item(i["asset_id"])  # public path
            if res.status != 404:
                leaks.append(i["asset_id"])
    if over or leaks:
        return InvariantResult(name, False,
                               f"above-tier collections listed: {over}; items visible: {leaks[:5]}")
    return InvariantResult(name, True, f"museum tier {museum_tier!r}; gate holds")


def check_contract_valid(client: ApiClient) -> InvariantResult:
    """Every publicly served item validates against the frozen contract v1.

    Verification code (not a persona action) may use the platform validator —
    the same one the build gate uses, so 'valid' means the same thing here
    and there.
    """
    name = "contrato-valido"
    from musa_build.contract import make_validator, validate_card

    validator = make_validator()
    bad = []
    count = 0
    for c in client.collections().body["data"]:
        res = client.collection_items(c["id"])
        for item in res.body["data"]:
            count += 1
            problems = validate_card(item, validator)
            if problems:
                bad.append(f"{item.get('asset_id')}: {problems[0]}")
    if bad:
        return InvariantResult(name, False, f"{len(bad)} invalid card(s): {bad[:3]}")
    return InvariantResult(name, True, f"{count} public item(s) valid against contract v1")


def check_build_green(repo: Path, frontend: Path, out_dir: Path,
                      builder_dir: Path) -> InvariantResult:
    """`musa-build build` on the current state finishes green."""
    name = "build-verde"
    proc = subprocess.run(
        [sys.executable, "-m", "musa_build", "build",
         "--repo", str(repo), "--frontend", str(frontend), "--out", str(out_dir)],
        cwd=str(builder_dir), capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        tail = (proc.stdout or "")[-400:] + (proc.stderr or "")[-400:]
        return InvariantResult(name, False, f"build exit {proc.returncode}: {tail}")
    return InvariantResult(name, True, "build finished green")


def standard_suite(client: ApiClient, museum_tier: str) -> list[InvariantResult]:
    """The fast invariants run after every routine (build-green is separate —
    it is slower and runs once per persona session)."""
    return [
        check_no_drafts_in_public(client),
        check_tier_gate(client, museum_tier),
        check_contract_valid(client),
    ]

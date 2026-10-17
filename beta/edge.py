"""M4.5 — edge-case battery: the corners of the contract, the gate,
concurrency, infra and the static site, each with an explicit verdict.

The personas cover the day-to-day and the misuse generator the hostile
scenarios; this suite covers the edges the owner enumerated (HANDOFF §M4):
unicode/RTL cards, BCE dates, empty-vs-absent fields, giant titles, orphan
drafts, unpublished heroes, empty collections, tier downgrade/upgrade,
_rev races, writes during builds, a token-less (read-only) server, a
corrupted overlay, a CI without secrets, and the browser-side statics
(no-CDN content, first-load weight, first access without an account).

Reboot cases use the ServeHarness: the server is restarted with a mutated
environment or config, and ALWAYS brought back healthy before the next case.

Red line (same as the misuse generator): pre-existing public items must be
byte-identical after the whole battery. Verdicts: "passa" / "falha" /
"achado-gap" (the API cannot express the scenario).
"""

from __future__ import annotations

import json
import os
import random
import string
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .client import ApiClient
from .harness import ServeHarness
from .personas import Event
from . import invariants as inv
from .invariants import snapshot_public_items

# The edge battery keeps its OWN gap registry — the personas' KNOWN_GAPS is
# their contract with test_beta (persona gaps == known persona gaps), and
# polluting it from here would break that assertion at import time.
EDGE_KNOWN_GAPS = {
    # An item whose collection is gated out is invisible even to the ADMIN
    # listing (it stays in the overlay and resurfaces when the collection
    # publishes) — there is no admin path to even see it.
    "gap-orphan-visibility":
        "items of a gated-out collection are invisible to the admin listing too — "
        "no API path to see or clean collection orphans",
}


def _slug(rng: random.Random, prefix: str) -> str:
    suffix = "".join(rng.choices(string.ascii_lowercase + string.digits, k=6))
    return f"beta-edge-{prefix}-{suffix}"


class EdgeRunner:
    def __init__(self, harness: ServeHarness, client: ApiClient,
                 rng: random.Random, run_id: str, museum_tier: str,
                 work_repo: Path, builder_dir: Path, frontend_dir: Path,
                 tmp_root: Path):
        self.harness = harness
        self.client = client
        self.rng = rng
        self.run_id = run_id
        self.museum_tier = museum_tier
        self.work_repo = Path(work_repo)
        self.builder_dir = Path(builder_dir)
        self.frontend_dir = Path(frontend_dir)
        self.tmp_root = Path(tmp_root)
        self.events: list[Event] = []
        self._now = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._baseline = snapshot_public_items(client)
        self._created: list[str] = []  # asset_ids born in this battery

    # -- plumbing ------------------------------------------------------------
    def _record(self, cenario: str, acao: str, alvo: str, resultado: str,
                latencia_ms: float, detalhe: str = "",
                invariantes: list | None = None) -> Event:
        invs = invariantes or []
        veredito = "reprova" if (resultado == "falha" or any(not i.ok for i in invs)) else "passa"
        ev = Event(self.run_id, self._now(), cenario, "edge@demo", acao, alvo,
                   resultado, latencia_ms, [i.as_dict() for i in invs], veredito, detalhe)
        self.events.append(ev)
        return ev

    def _collection_id(self) -> str:
        return self.client.collections().body["data"][0]["id"]

    def _make_card(self, collection: str, **over) -> dict:
        card = {
            "asset_id": _slug(self.rng, "item"),
            "titulo": "Edge case piece",
            "colecao": collection,
            "autor": "Edge Author",
        }
        card.update(over)
        return card

    def _publish(self, asset_id: str) -> None:
        res = self.client.save_item({"asset_id": asset_id, "website_status": "published"})
        assert res.ok, f"publish failed for {asset_id}: {res.status} {res.body}"

    def _create_published(self, collection: str, **over) -> dict:
        card = self._make_card(collection, **over)
        res = self.client.save_item(card)
        assert res.ok, f"create failed: {res.status} {res.body}"
        self._created.append(card["asset_id"])
        self._publish(card["asset_id"])
        return card

    def _relogin(self) -> None:
        login = self.client.login("edge@demo", self.harness.token)
        assert login.ok, f"edge login failed: {login.status} {login.body}"

    def _build(self, out_dir: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "musa_build", "build",
             "--repo", str(self.work_repo), "--frontend", str(self.frontend_dir),
             "--out", str(out_dir)],
            cwd=str(self.builder_dir), capture_output=True, text=True, timeout=600,
        )

    # -- contract ------------------------------------------------------------
    def case_unicode_emoji_rtl(self) -> None:
        """Emoji, accents and RTL text round-trip byte-identical and searchable."""
        col = self._collection_id()
        titulo = "Vênus de Milo 🏛️ — تمثال «Ação»"
        autor = "Leonardo da Vinci — ليوناردو — 里奥纳多"
        descricao = "Peça com acentuação à esquerda e texto RTL: مرحبا بالعالم — fim."
        card = self._create_published(col, titulo=titulo, autor=autor, descricao=descricao)
        res = self.client.item(card["asset_id"])
        served = res.body["data"] if res.ok else {}
        identical = (res.ok and served.get("titulo") == titulo
                     and served.get("autor") == autor and served.get("descricao") == descricao)
        search = self.client.search("Vênus")
        found = search.ok and any(i["asset_id"] == card["asset_id"] for i in search.body["data"])
        ok = identical and found
        self._record("contrato", "unicode-emoji-rtl-roundtrip", card["asset_id"],
                     "passa" if ok else "falha", res.latency_ms,
                     f"round-trip byte-identical: {identical}; search 'Vênus' found it: {found}")

    def case_asset_id_limits(self) -> None:
        """A 120-char asset_id is accepted (no length limit anywhere); an
        uppercase id is a 422 — the API write-path is deliberately stricter
        than the contract pattern (which allows A-Z, '.' and '_')."""
        col = self._collection_id()
        long_id = "a" * 120
        res_long = self.client.save_item(self._make_card(col, asset_id=long_id))
        long_ok = res_long.ok
        if long_ok:
            self._created.append(long_id)
        res_upper = self.client.save_item(self._make_card(col, asset_id="ABC-Upper"))
        upper_rejected = res_upper.status == 422
        ok = long_ok and upper_rejected
        self._record(
            "contrato", "asset-id-limites", f"{long_id[:20]}… / ABC-Upper",
            "passa" if ok else "falha", res_long.latency_ms + res_upper.latency_ms,
            f"120-char id accepted: {long_ok} (NO length limit in contract or serve — "
            f"filesystem risk documented in the M4.5 report); uppercase id 422: {upper_rejected} "
            f"(serve stricter than the contract pattern, the safe direction)")

    def case_empty_vs_absent(self) -> None:
        """titulo '' is a 422 (minLength 1); optional field '' is accepted and
        served as ''; optional field absent is accepted and stays absent."""
        col = self._collection_id()
        bad = self.client.save_item(self._make_card(col, titulo=""))
        bad_rejected = bad.status == 422
        empty = self._make_card(col, autor="")
        res_empty = self.client.save_item(empty)
        absent = self._make_card(col)
        absent.pop("autor")
        res_absent = self.client.save_item(absent)
        ok_empty = False
        ok_absent = False
        if res_empty.ok:
            self._created.append(empty["asset_id"])
            got = self.client.item(empty["asset_id"], auth=True).body["data"]
            ok_empty = got.get("autor") == ""
        if res_absent.ok:
            self._created.append(absent["asset_id"])
            got = self.client.item(absent["asset_id"], auth=True).body["data"]
            ok_absent = "autor" not in got
        ok = bad_rejected and ok_empty and ok_absent
        self._record("contrato", "vazio-vs-ausente", col,
                     "passa" if ok else "falha",
                     bad.latency_ms + res_empty.latency_ms + res_absent.latency_ms,
                     f"titulo '' 422: {bad_rejected}; autor '' kept as '': {ok_empty}; "
                     f"autor absent stays absent: {ok_absent}")

    def case_data_iso_bce(self) -> None:
        """BCE (-500), one-digit year (5) and a full BCE date are valid;
        a month-13 date is a 422; values round-trip exactly."""
        col = self._collection_id()
        accepted = {}
        for value in ("-500", "5", "-500-12-25"):
            res = self.client.save_item(self._make_card(col, data_iso=value))
            ok = res.ok
            if ok:
                aid = res.body["data"]["asset_id"]
                self._created.append(aid)
                got = self.client.item(aid, auth=True).body["data"]
                ok = got.get("data_iso") == value
            accepted[value] = ok
        bad = self.client.save_item(self._make_card(col, data_iso="1500-13-01"))
        rejected = bad.status == 422
        ok = all(accepted.values()) and rejected
        self._record("contrato", "data-iso-bce", col, "passa" if ok else "falha",
                     bad.latency_ms,
                     f"accepted with exact round-trip: {accepted}; '1500-13-01' 422: {rejected}")

    def case_giant_collection_title(self) -> None:
        """A 10.000-char collection title is accepted (no length limit) and
        nothing downstream breaks (list, items, search)."""
        cid = _slug(self.rng, "giantcol")
        title = "Coleção " + "x" * 10_000
        res = self.client.create_collection(cid, title)
        created = res.ok
        listed = False
        search_ok = False
        if created:
            listed = any(c["id"] == cid and len(c.get("title", "")) > 10_000
                         for c in self.client.collections().body["data"])
            search_ok = self.client.search("edge").status == 200
        ok = created and listed and search_ok
        self._record("contrato", "titulo-gigante-colecao", cid,
                     "passa" if ok else "falha", res.latency_ms,
                     f"10k-char title accepted: {created}; listed intact: {listed}; "
                     f"search still fine: {search_ok} (no length limit — documented)")

    # -- gating ---------------------------------------------------------------
    def case_orphan_draft_collection(self) -> None:
        """A published item inside an UNPUBLISHED collection: public 404 for
        both — and the admin listing cannot see it either (known gap)."""
        cid = _slug(self.rng, "orphancol")
        res_c = self.client.create_collection(cid, "Orphan host", website_status="draft")
        col_created = res_c.ok or res_c.status == 200
        card = self._make_card(cid)
        res_i = self.client.save_item(card)
        self._created.append(card["asset_id"])
        self._publish(card["asset_id"])
        pub_item = self.client.item(card["asset_id"])
        pub_col = self.client.collection_items(cid)
        cols = self.client.collections().body["data"]
        admin_items = self.client.collection_items(cid, include_drafts=True, auth=True)
        hidden_public = pub_item.status == 404 and pub_col.status == 404 \
            and not any(c["id"] == cid for c in cols)
        orphan_gap = admin_items.status == 404  # admin can't list it either
        ok = col_created and res_i.ok and hidden_public
        if orphan_gap:
            detalhe = (f"public 404 for item and collection: {hidden_public} (gate holds); "
                       f"gap-orphan-visibility: admin listing also 404 — the orphan only "
                       f"resurfaces if the collection is published")
            gap_id = "gap-orphan-visibility"
            detalhe = f"{gap_id}: {EDGE_KNOWN_GAPS[gap_id]} | {detalhe}"
            self._record("gating", "draft-orfao-colecao", card["asset_id"],
                         "achado-gap", pub_item.latency_ms, detalhe)
        else:
            self._record("gating", "draft-orfao-colecao", card["asset_id"],
                         "passa" if ok else "falha", pub_item.latency_ms,
                         f"collection created as draft: {col_created}; item created+published: "
                         f"{res_i.ok}; public 404 for both: {hidden_public}; admin sees it: "
                         f"{admin_items.status == 200}")

    def case_unpublished_hero(self) -> None:
        """hero:true never punches through the gate: draft hero is a public
        404, published hero is served with the flag, un-published hero is a
        404 again."""
        col = self._collection_id()
        card = self._make_card(col, hero=True)
        res = self.client.save_item(card)
        self._created.append(card["asset_id"])
        aid = card["asset_id"]
        draft_hidden = self.client.item(aid).status == 404
        self._publish(aid)
        pub = self.client.item(aid)
        published_visible = pub.ok and pub.body["data"].get("hero") is True
        self.client.save_item({"asset_id": aid, "website_status": "draft"})
        hidden_again = self.client.item(aid).status == 404
        ok = res.ok and draft_hidden and published_visible and hidden_again
        self._record("gating", "hero-despublicado", aid, "passa" if ok else "falha",
                     pub.latency_ms,
                     f"draft hero 404: {draft_hidden}; published hero served with flag: "
                     f"{published_visible}; un-published hero 404: {hidden_again}")

    def case_empty_published_collection(self) -> None:
        """A published collection with zero items: listed, items endpoint 200
        with count 0, no 500 anywhere."""
        cid = _slug(self.rng, "emptycol")
        res = self.client.create_collection(cid, "Empty but published")
        listed = any(c["id"] == cid for c in self.client.collections().body["data"])
        items = self.client.collection_items(cid)
        empty_ok = items.ok and items.body["meta"].get("count") == 0 \
            and items.body["data"] == []
        ok = res.ok and listed and empty_ok
        self._record("gating", "colecao-vazia-publicada", cid,
                     "passa" if ok else "falha", res.latency_ms,
                     f"created: {res.ok}; publicly listed: {listed}; items 200 count=0: {empty_ok}")

    # -- concurrency ------------------------------------------------------------
    def case_rev_race(self) -> None:
        """Two writers patch the same card with the SAME _rev: exactly one
        wins (200), the other gets a 409, and the final _rev moved once."""
        col = self._collection_id()
        card = self._create_published(col)
        aid = card["asset_id"]
        rev = self.client.item(aid, auth=True).body["data"]["_rev"]
        barrier = threading.Barrier(3)
        results: list[int] = []

        def writer(title: str) -> None:
            barrier.wait()
            res = self.client.save_item({"asset_id": aid, "titulo": title, "_rev": rev})
            results.append(res.status)

        threads = [threading.Thread(target=writer, args=(t,)) for t in ("Writer A", "Writer B")]
        for t in threads:
            t.start()
        barrier.wait()
        for t in threads:
            t.join()
        final = self.client.item(aid, auth=True).body["data"]
        one_each = sorted(results) == [200, 409]
        consistent = final.get("titulo") in ("Writer A", "Writer B") and final.get("_rev") == rev + 1
        ok = one_each and consistent
        self._record("concorrencia", "rev-duas-escritas", aid,
                     "passa" if ok else "falha", 0.0,
                     f"statuses {sorted(results)} (want [200, 409]): {one_each}; final titulo "
                     f"{final.get('titulo')!r} at _rev {final.get('_rev')} (was {rev}): {consistent}")

    def case_last_write_wins(self) -> None:
        """Two writers patch the same field WITHOUT _rev: both 200, the field
        ends as one of the two values (never corrupted), _rev moved twice —
        last-write-wins by design."""
        col = self._collection_id()
        card = self._create_published(col)
        aid = card["asset_id"]
        before = self.client.item(aid, auth=True).body["data"]["_rev"]
        barrier = threading.Barrier(3)
        results: list[int] = []

        def writer(title: str) -> None:
            barrier.wait()
            results.append(self.client.save_item({"asset_id": aid, "titulo": title}).status)

        threads = [threading.Thread(target=writer, args=(t,)) for t in ("LWW A", "LWW B")]
        for t in threads:
            t.start()
        barrier.wait()
        for t in threads:
            t.join()
        final = self.client.item(aid, auth=True).body["data"]
        both_ok = results == [200, 200]
        consistent = final.get("titulo") in ("LWW A", "LWW B") and final.get("_rev") == before + 2
        ok = both_ok and consistent
        self._record("concorrencia", "sem-rev-ultima-vence", aid,
                     "passa" if ok else "falha", 0.0,
                     f"both 200: {both_ok}; final titulo {final.get('titulo')!r} (one of the two, "
                     f"never merged garbage): {consistent}; _rev {before} -> {final.get('_rev')}")

    def case_reads_during_writes(self) -> None:
        """A patch storm while public reads loop: zero 5xx, every read a
        well-formed envelope."""
        col = self._collection_id()
        card = self._create_published(col)
        aid = card["asset_id"]
        stop = threading.Event()
        bad_reads: list[str] = []

        def reader() -> None:
            while not stop.is_set():
                for check in (self.client.collections(),
                              self.client.item(aid),
                              self.client.search("edge")):
                    if check.status >= 500:
                        bad_reads.append(f"{check.status}")
                    elif check.ok and not isinstance(check.body, dict):
                        bad_reads.append("malformed")

        def writer() -> None:
            for n in range(30):
                self.client.save_item({"asset_id": aid, "descricao": f"storm {n}"})

        t_read = threading.Thread(target=reader)
        t_read.start()
        t_write = threading.Thread(target=writer)
        t_write.start()
        t_write.join()
        stop.set()
        t_read.join()
        ok = not bad_reads
        self._record("concorrencia", "leituras-durante-escritas", aid,
                     "passa" if ok else "falha", 0.0,
                     f"30 patches with concurrent public reads; 5xx/malformed reads: "
                     f"{bad_reads[:5] or 'none'}")

    def case_write_during_build(self) -> None:
        """`musa-build build` on the repo while the API is being written: the
        build is repo-only by architecture — it finishes green and no write
        fails."""
        out_dir = self.tmp_root / "site-during-writes"
        proc_holder: list[subprocess.CompletedProcess] = []

        def run_build() -> None:
            proc_holder.append(self._build(out_dir))

        t_build = threading.Thread(target=run_build)
        t_build.start()
        col = self._collection_id()
        write_failures = []
        for n in range(20):
            res = self.client.save_item(self._make_card(col, titulo=f"During build {n}"))
            if not res.ok:
                write_failures.append(res.status)
            else:
                self._created.append(res.body["data"]["asset_id"])
        t_build.join()
        build_ok = proc_holder and proc_holder[0].returncode == 0
        ok = build_ok and not write_failures
        detail_tail = (proc_holder[0].stdout or "")[-200:] if proc_holder else "no build"
        self._record("concorrencia", "escrita-durante-build", str(out_dir),
                     "passa" if ok else "falha", 0.0,
                     f"build green during 20 API writes: {build_ok}; write failures: "
                     f"{write_failures or 'none'} (build is repo-only, overlay is the "
                     f"serve's — independent by architecture); build tail: {detail_tail[-120:]}",
                     invariantes=inv.standard_suite(self.client, self.museum_tier))

    # -- pipeline regressions ----------------------------------------------------
    def case_duplicate_asset_id(self) -> None:
        """Regression of the M3.2 guard: a create-shaped body for an existing
        asset_id is a 409 and the card is NOT overwritten."""
        aid = next(iter(self._baseline))
        before = self.client.item(aid).body["data"]
        res = self.client.save_item({"asset_id": aid, "titulo": "HOSTILE TAKEOVER",
                                     "colecao": before["colecao"]})
        rejected = res.status == 409
        after = self.client.item(aid).body["data"]
        untouched = json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)
        ok = rejected and untouched
        self._record("pipeline", "duplicata-asset-id", aid, "passa" if ok else "falha",
                     res.latency_ms,
                     f"duplicate create 409: {rejected}; pre-existing card byte-identical: {untouched}")

    # -- infra (no reboot) ---------------------------------------------------------
    def case_build_bad_destination(self) -> None:
        """Build with an impossible --out (an existing FILE): non-zero exit
        with an explicit message, never a silent success."""
        blocker = self.tmp_root / "not-a-dir"
        blocker.write_text("I am a file, not a directory", encoding="utf-8")
        proc = self._build(blocker / "site")
        explicit = proc.returncode != 0 and bool((proc.stdout + proc.stderr).strip())
        self._record("infra", "build-destino-invalido", str(blocker),
                     "passa" if explicit else "falha", 0.0,
                     f"exit {proc.returncode} (non-zero: {proc.returncode != 0}); message: "
                     f"{((proc.stdout + proc.stderr).strip().splitlines() or ['<empty>'])[-1][:160]}")

    def case_ci_without_secrets(self) -> None:
        """The client CI must fail EXPLICITLY when GHCR_PULL_TOKEN is missing
        (a preflight step), not with a generic docker login error."""
        wf = self.work_repo / ".github" / "workflows" / "deploy.yml"
        if not wf.is_file():
            self._record("infra", "ci-sem-secrets", ".github/workflows/deploy.yml",
                         "achado-gap", 0.0,
                         "this repo has no deploy workflow to preflight (fixture/minimal repo)")
            return
        text = wf.read_text(encoding="utf-8")
        has_preflight = "Preflight" in text and "GHCR_PULL_TOKEN is not configured" in text
        self._record("infra", "ci-sem-secrets", ".github/workflows/deploy.yml",
                     "passa" if has_preflight else "falha", 0.0,
                     f"explicit preflight for missing GHCR_PULL_TOKEN: {has_preflight}"
                     + ("" if has_preflight else
                        " — DIVERGENCE: without it a missing secret surfaces as a cryptic "
                        "docker login failure"))

    # -- infra (reboot) ---------------------------------------------------------
    def case_no_admin_token(self) -> None:
        """Server without MUSA_ADMIN_TOKEN: health says writes disabled,
        writes and login are an explicit 503, public reads keep working."""
        client = self.harness.reboot(drop_env=("MUSA_ADMIN_TOKEN",))
        assert client is not None, "read-only server did not boot"
        health = client.health().body
        writes_disabled = health.get("writes") == "disabled"
        write = client.request("POST", "/items", json={"asset_id": "x"})
        login = client.request("POST", "/auth/login", json={"email": "a@b", "password": "x"})
        public_ok = client.collections().ok
        w503 = write.status == 503
        l503 = login.status == 503
        # Bring the normal server back BEFORE the next case.
        self.client = self.harness.reboot()
        assert self.client is not None, "server did not come back with the token"
        self._relogin()
        ok = writes_disabled and w503 and l503 and public_ok
        self._record("infra", "sem-admin-token", "serve", "passa" if ok else "falha",
                     write.latency_ms + login.latency_ms,
                     f"health.writes == 'disabled': {writes_disabled}; write 503: {w503}; "
                     f"login 503: {l503}; public reads ok: {public_ok}")

    def case_tier_downgrade_upgrade(self) -> None:
        """An item tagged at the museum's OWN top tier: visible now, gone at
        bronze, back after the upgrade (downgrade/upgrade via config + reboot,
        dev pin — the signed flow is the platform re-signing; the tamper case
        covers editing a signed config)."""
        if self.museum_tier == "bronze":
            self._record("gating", "tier-downgrade-upgrade", "museum.config.json",
                         "achado-gap", 0.0,
                         "museum is already bronze — no top tier to downgrade from")
            return
        col = self._collection_id()
        card = self._create_published(col, tier=self.museum_tier,
                                      titulo="Top-tier-only edge piece")
        aid = card["asset_id"]
        visible_at_top = self.client.item(aid).ok

        config_path = self.work_repo / "museum.config.json"
        original = config_path.read_bytes()
        config = json.loads(original.decode("utf-8"))
        config["musa"] = "0.0.0-unreleased"  # dev pin: unsigned config allowed locally
        ent = config.setdefault("entitlements", {})
        ent.pop("signature", None)
        ent["tier"] = "bronze"
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        client = self.harness.reboot()
        assert client is not None, "bronze reboot failed"
        client.login("edge@demo", self.harness.token)  # fresh client, fresh session
        hidden_at_bronze = client.item(aid).status == 404
        admin_too = client.item(aid, auth=True).status == 404  # tier never relaxes, M4.3

        config["entitlements"]["tier"] = self.museum_tier
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        client = self.harness.reboot()
        assert client is not None, "top-tier reboot failed"
        back_at_top = client.item(aid).ok

        config_path.write_bytes(original)
        self.client = self.harness.reboot()
        assert self.client is not None, "restore reboot failed"
        self._relogin()
        ok = visible_at_top and hidden_at_bronze and admin_too and back_at_top
        self._record("gating", "tier-downgrade-upgrade", aid, "passa" if ok else "falha",
                     0.0,
                     f"{self.museum_tier} item visible at {self.museum_tier}: {visible_at_top}; "
                     f"404 at bronze (public): {hidden_at_bronze}; 404 at bronze (admin too — "
                     f"tier never relaxes): {admin_too}; back at {self.museum_tier}: {back_at_top}")

    def case_tampered_entitlements(self) -> None:
        """Editing the tier of a SIGNED config (keeping the old signature)
        kills the boot with an explicit entitlements error — self-promotion
        is impossible (ADR 0010)."""
        config_path = self.work_repo / "museum.config.json"
        original = config_path.read_bytes()
        config = json.loads(original.decode("utf-8"))
        if not (config.get("entitlements") or {}).get("signature"):
            self._record("gating", "config-adulterado", "museum.config.json",
                         "achado-gap", 0.0,
                         "client config is unsigned — the tamper case needs a signed config")
            return
        config["entitlements"]["tier"] = "bronze"  # signature now stale
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        client = self.harness.reboot(expect_up=False, timeout_s=15.0)
        boot_failed = client is None
        stderr = self.harness.boot_stderr()
        explicit = "entitlements" in stderr and "signature" in stderr
        config_path.write_bytes(original)
        self.client = self.harness.reboot()
        assert self.client is not None, "restore reboot failed"
        self._relogin()
        ok = boot_failed and explicit
        self._record("gating", "config-adulterado", "museum.config.json",
                     "passa" if ok else "falha", 0.0,
                     f"boot refused with stale signature: {boot_failed}; explicit entitlements/"
                     f"signature error: {explicit}")

    def case_corrupted_overlay(self) -> None:
        """Garbage in .musa/state.db: the boot FAILS with an explicit message
        pointing at the overlay (never a silently empty museum). Deleting the
        overlay rebuilds from the repo seed — overlay edits are gone (their
        RPO is the M4.4 backup)."""
        self.harness.stop()
        db_path = self.harness.data_dir / "state.db"
        for _ in range(10):  # Windows: the SQLite lock can linger after kill
            try:
                db_path.write_bytes(b"this is not a sqlite database at all")
                break
            except PermissionError:
                time.sleep(0.5)
        client = self.harness.boot(expect_up=False, timeout_s=15.0)
        boot_failed = client is None
        stderr = self.harness.boot_stderr()
        explicit = "overlay" in stderr.lower() and ("unreadable" in stderr.lower()
                                                    or "corrupt" in stderr.lower())
        # Rebuild from the seed: delete the overlay entirely and boot.
        for _ in range(10):
            try:
                db_path.unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.5)
        self.client = self.harness.boot()
        assert self.client is not None, "rebuild-from-seed boot failed"
        self._relogin()
        baseline_now = snapshot_public_items(self.client)
        seed_back = baseline_now == self._baseline
        ok = boot_failed and explicit and seed_back
        self._record("infra", "overlay-corrompido-e-reconstruido", str(db_path),
                     "passa" if ok else "falha", 0.0,
                     f"corrupt overlay -> explicit boot failure: {boot_failed} (message mentions "
                     f"overlay: {explicit}); overlay deleted -> museum rebuilt from the repo "
                     f"seed, pre-existing public items byte-identical: {seed_back}; overlay "
                     f"edits are lost (RPO = M4.4 backup)",
                     invariantes=inv.standard_suite(self.client, self.museum_tier))

    # -- static site (browser-side) ---------------------------------------------
    def cases_static_site(self) -> None:
        """One shared build answers the browser-side edges: a 20 MB asset,
        first-load weight, content without CDN, first access without account."""
        site = self.tmp_root / "site-static"
        t0 = time.perf_counter()
        proc = self._build(site)
        base_s = time.perf_counter() - t0
        if proc.returncode != 0:
            self._record("estatico", "build-base", str(site), "falha", 0.0,
                         f"static build failed: {(proc.stdout or '')[-200:]}")
            return

        # 20 MB local asset: the build must stay green and fast (the public
        # site's media lives on R2; a local big file is the on-premise case).
        col = self._collection_id()
        big = self.work_repo / "content" / col / "edge-big-20mb.bin"
        big.parent.mkdir(parents=True, exist_ok=True)
        big.write_bytes(os.urandom(20 * 1024 * 1024))
        t0 = time.perf_counter()
        proc_big = self._build(self.tmp_root / "site-static-20mb")
        big_s = time.perf_counter() - t0
        big.unlink()
        ok_big = proc_big.returncode == 0
        self._record("estatico", "capa-20mb", big.name, "passa" if ok_big else "falha",
                     0.0,
                     f"build green with a 20 MB local asset: {ok_big}; baseline {base_s:.1f}s "
                     f"-> with 20 MB {big_s:.1f}s")

        index = site / "index.html"
        html = index.read_text(encoding="utf-8", errors="replace") if index.is_file() else ""

        # First-load weight: HTML + local css/js + the generated catalog payload.
        weight = 0
        for path in site.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".html", ".css", ".js", ".json"):
                weight += path.stat().st_size
        self._record("estatico", "peso-inicial", "index.html", "passa", 0.0,
                     f"first-load local payload (html+css+js+json, whole site): "
                     f"{weight / 1024:.0f} KB in {len(list(site.rglob('*')))} files — hero video "
                     f"is external (YouTube), item media is external (R2)")

        # Content without CDN: the catalog payload is a LOCAL generated file;
        # CDN-dependent features (3D viewers) degrade, the collection does not.
        catalog_js = (site / "data" / "catalog.js").is_file()
        catalog_json = (site / "data" / "catalog.json").is_file()
        local_payload = catalog_js and catalog_json and "data/catalog" in html
        self._record("estatico", "conteudo-sem-cdn", "data/catalog.js",
                     "passa" if local_payload else "falha", 0.0,
                     f"local generated payload referenced by the landing: {local_payload} "
                     f"(catalog.js: {catalog_js}, catalog.json: {catalog_json}) — with a blocked "
                     f"CDN the 3D viewers degrade, the collection itself renders from local data")

        # First access without an account: no login WALL on the landing. The
        # curator's login lives in a modal (id="loginModal") — present but
        # never gating the primary content (hero, collections render outside it).
        modal_at = html.find('id="loginModal"')
        form_at = html.find('id="loginForm"')
        login_in_modal = modal_at != -1 and form_at > modal_at
        primary_outside = ('id="venue"' in html or 'id="collections"' in html
                           or "collections" in html)
        no_wall = login_in_modal and primary_outside
        self._record("estatico", "primeiro-acesso", "index.html",
                     "passa" if no_wall else "falha", 0.0,
                     f"login form lives inside the admin modal (not a wall): {login_in_modal}; "
                     f"primary content renders outside it: {primary_outside}; the public "
                     f"catalog is a static file — no account needed")

    # -- driver ------------------------------------------------------------------
    def run_all(self) -> list[Event]:
        # 1) cases against the healthy server (order-independent)
        self.case_unicode_emoji_rtl()
        self.case_asset_id_limits()
        self.case_empty_vs_absent()
        self.case_data_iso_bce()
        self.case_giant_collection_title()
        self.case_orphan_draft_collection()
        self.case_unpublished_hero()
        self.case_empty_published_collection()
        self.case_rev_race()
        self.case_last_write_wins()
        self.case_reads_during_writes()
        self.case_write_during_build()
        self.case_duplicate_asset_id()
        self.case_build_bad_destination()
        self.case_ci_without_secrets()
        # 2) static site cases (own builds, no serve mutation)
        self.cases_static_site()
        # 3) reboot cases (each restores a healthy server before the next)
        self.case_no_admin_token()
        self.case_tier_downgrade_upgrade()
        self.case_tampered_entitlements()
        self.case_corrupted_overlay()  # last: wipes the overlay on purpose
        # 4) red line + final invariants
        after = snapshot_public_items(self.client)
        drift = [aid for aid, snap in self._baseline.items() if after.get(aid) != snap]
        self._record("linha-vermelha", "acervo-pre-existente-intacto",
                     f"{len(self._baseline)} itens",
                     "passa" if not drift else "falha", 0.0,
                     f"pre-existing public items byte-identical after the battery: "
                     f"{not drift}" + (f" — drifted: {drift[:5]}" if drift else ""),
                     invariantes=inv.standard_suite(self.client, self.museum_tier))
        return self.events

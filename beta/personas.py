"""Synthetic personas for the M3 virtual client (ADR 0014).

`owner@demo` and `team@demo` operate the DemoMuseum through the public HTTP
API only. Every routine is deterministic under a seed: same seed + same
starting state => same action sequence. Routines that the API cannot express
are recorded as first-class gap findings — never worked around with builder
internals (plan M3 restriction no. 1).
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .client import ApiClient, ApiResponse
from . import invariants as inv

# Gaps already known before the first run (M3_plano.md header). A persona
# hitting one logs resultado="achado-gap" with this id — expected finding,
# not a regression. A NEW gap id is a genuine discovery.
KNOWN_GAPS = {
    "gap-upload-endpoint": "no asset upload endpoint; curator path is the musa-build upload CLI",
    "gap-collection-edit-endpoint": "no PATCH /collections — subcollection reorganization is impossible via API",
    "gap-undo-endpoint": "no undo endpoint; undo is a manual patch back to the previous value",
    "gap-module-request-channel": "no endpoint to request a new module — feature requests have no channel",
}


@dataclass
class Event:
    run_id: str
    timestamp: str
    cenario: str
    persona: str
    acao: str
    alvo: str
    resultado: str          # "ok" | "falha" | "achado-gap"
    latencia_ms: float
    invariantes: list[dict] = field(default_factory=list)
    veredito: str = "passa"  # "passa" | "reprova"
    detalhe: str = ""

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "cenario": self.cenario,
            "persona": self.persona,
            "acao": self.acao,
            "alvo": self.alvo,
            "resultado": self.resultado,
            "latencia_ms": round(self.latencia_ms, 1),
            "invariantes": self.invariantes,
            "veredito": self.veredito,
            "detalhe": self.detalhe,
        }


class Persona:
    """One synthetic curator. `scope` limits which routines it may run
    (team@demo has a narrower scope until real roles exist — ADR 0008)."""

    def __init__(self, email: str, client: ApiClient, rng: random.Random,
                 run_id: str, museum_tier: str):
        self.email = email
        self.client = client
        self.rng = rng
        self.run_id = run_id
        self.museum_tier = museum_tier
        self.events: list[Event] = []

    # -- plumbing -------------------------------------------------------
    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _slug(self, prefix: str) -> str:
        # Deterministic suffix from the persona's own rng stream.
        suffix = "".join(self.rng.choices(string.ascii_lowercase + string.digits, k=6))
        return f"beta-{prefix}-{suffix}"

    def _record(self, cenario: str, acao: str, alvo: str, resultado: str,
                latencia_ms: float, detalhe: str = "",
                invariantes: list[inv.InvariantResult] | None = None) -> Event:
        invs = invariantes or []
        veredito = "passa"
        if resultado == "falha" or any(not i.ok for i in invs):
            veredito = "reprova"
        ev = Event(self.run_id, self._now(), cenario, self.email, acao, alvo,
                   resultado, latencia_ms, [i.as_dict() for i in invs], veredito, detalhe)
        self.events.append(ev)
        return ev

    def _gap(self, cenario: str, acao: str, alvo: str, gap_id: str,
             res: ApiResponse) -> Event:
        known = gap_id in KNOWN_GAPS
        detalhe = f"{gap_id}: {KNOWN_GAPS.get(gap_id, 'NEW GAP — not in the known list')} (HTTP {res.status})"
        return self._record(cenario, acao, alvo, "achado-gap", res.latency_ms, detalhe)

    def _suite(self) -> list[inv.InvariantResult]:
        return inv.standard_suite(self.client, self.museum_tier)

    def _published_items(self) -> list[dict]:
        items = []
        for c in self.client.collections().body["data"]:
            res = self.client.collection_items(c["id"])
            if res.ok:
                items.extend(res.body["data"])
        return items

    def _random_collection_with_items(self) -> tuple[dict, list[dict]]:
        found = self._collection_with_min_items(1)
        if found is None:
            raise RuntimeError("no public collection with items — cannot run persona routines")
        return found

    def _collection_with_min_items(self, n: int) -> tuple[dict, list[dict]] | None:
        """First collection (shuffled by the persona rng) with >= n published
        items, or None. Deterministic given the seed and the live state."""
        cols = self.client.collections().body["data"]
        self.rng.shuffle(cols)
        for c in cols:
            res = self.client.collection_items(c["id"])
            if res.ok:
                published = [i for i in res.body["data"]
                             if i.get("website_status") == "published"]
                if len(published) >= n:
                    return c, res.body["data"]
        return None

    # -- routines ---------------------------------------------------------
    def daily(self) -> list[Event]:
        """Publish 2 items, correct one card, upload one image."""
        cenario = "diaria"
        col, items = self._random_collection_with_items()

        # 1. publish 2 items: create (born draft) -> must be invisible publicly
        #    -> patch to published -> must appear publicly.
        for _ in range(2):
            asset_id = self._slug("item")
            card = {
                "asset_id": asset_id,
                "titulo": f"Peça beta {asset_id}",
                "colecao": col["id"],
                "autor": "Persona Sintética",
                "data": "2026",
                "material": "Digital",
                "descricao": "Item criado pela rotina diária do cliente virtual.",
                "tags": ["beta"],
            }
            total_ms = 0.0
            res = self.client.save_item(card)
            total_ms += res.latency_ms
            if not res.ok:
                self._record(cenario, "publicar-item", asset_id, "falha", total_ms,
                             f"create failed: HTTP {res.status} {res.body}")
                continue
            pub_probe = self.client.item(asset_id)  # public path, no token
            total_ms += pub_probe.latency_ms
            if pub_probe.status != 404:
                self._record(cenario, "publicar-item", asset_id, "falha", total_ms,
                             f"draft visible publicly (HTTP {pub_probe.status}) before publish")
                continue
            res = self.client.save_item({"asset_id": asset_id, "website_status": "published"})
            total_ms += res.latency_ms
            probe = self.client.item(asset_id)
            total_ms += probe.latency_ms
            if res.ok and probe.ok:
                self._record(cenario, "publicar-item", asset_id, "ok", total_ms,
                             "draft -> published, visible publicly",
                             invariantes=self._suite())
            else:
                self._record(cenario, "publicar-item", asset_id, "falha", total_ms,
                             f"publish patch HTTP {res.status}; public probe HTTP {probe.status}")

        # 2. correct a card: patch one field of a published item.
        target = self.rng.choice(items)
        before = self.client.item(target["asset_id"], auth=True)
        old_desc = (before.body["data"].get("descricao") or "") if before.ok else ""
        marker = " [corrigido pelo cliente virtual]"
        res = self.client.save_item({"asset_id": target["asset_id"],
                                     "descricao": old_desc + marker})
        after = self.client.item(target["asset_id"])
        total_ms = res.latency_ms + after.latency_ms
        if res.ok and after.ok and after.body["data"].get("descricao", "").endswith(marker):
            self._record(cenario, "corrigir-card", target["asset_id"], "ok", total_ms,
                         "descricao patched and visible publicly",
                         invariantes=self._suite())
        else:
            self._record(cenario, "corrigir-card", target["asset_id"], "falha", total_ms,
                         f"patch HTTP {res.status}; reread ok={after.ok}")

        # 3. upload an image: the API has no asset endpoint (known gap).
        res = self.client.request("POST", "/assets", auth=True,
                                  json={"asset_id": self._slug("asset"), "filename": "foto.jpg"})
        self._gap(cenario, "subir-imagem", "/assets", "gap-upload-endpoint", res)
        return self.events

    def weekly(self) -> list[Event]:
        """Create a collection, reorganize a subcollection, promote a hero."""
        cenario = "semanal"

        # 1. create a collection.
        cid = self._slug("colecao")
        res = self.client.create_collection(cid, f"Coleção beta {cid}")
        if res.ok:
            self._record(cenario, "criar-colecao", cid, "ok", res.latency_ms,
                         f"HTTP {res.status}", invariantes=self._suite())
        else:
            self._record(cenario, "criar-colecao", cid, "falha", res.latency_ms,
                         f"HTTP {res.status} {res.body}")

        # 2. reorganize a subcollection: no collection edit endpoint (known gap).
        res = self.client.request("PATCH", f"/collections/{cid}", auth=True,
                                  json={"subcollections": []})
        self._gap(cenario, "reorganizar-subcolecao", cid, "gap-collection-edit-endpoint", res)

        # 3. promote a hero: clear hero on current, set on a random peer.
        found = self._collection_with_min_items(2)
        if found is None:
            # Not a product failure: a small museum legitimately has no
            # collection with 2+ published items. Recorded as a skip.
            self._record(cenario, "promover-hero", "-", "pulada", 0.0,
                         "no collection with 2+ published items")
            return self.events
        col, items = found
        published = [i for i in items if i.get("website_status") == "published"]
        current = next((i for i in published if i.get("hero")), None)
        candidates = [i for i in published if i is not current]
        new_hero = self.rng.choice(candidates)
        total_ms = 0.0
        if current:
            r1 = self.client.save_item({"asset_id": current["asset_id"], "hero": False})
            total_ms += r1.latency_ms
        r2 = self.client.save_item({"asset_id": new_hero["asset_id"], "hero": True})
        total_ms += r2.latency_ms
        probe = self.client.item(new_hero["asset_id"])
        total_ms += probe.latency_ms
        if r2.ok and probe.ok and probe.body["data"].get("hero"):
            self._record(cenario, "promover-hero", new_hero["asset_id"], "ok", total_ms,
                         f"hero moved within {col['id']}", invariantes=self._suite())
        else:
            self._record(cenario, "promover-hero", new_hero["asset_id"], "falha",
                         total_ms, f"patch HTTP {r2.status}; probe hero={probe.ok}")
        return self.events

    def punctual(self) -> list[Event]:
        """Unpublish, undo, request a new module."""
        cenario = "pontual"
        col, items = self._random_collection_with_items()

        # 1. unpublish: patch back to draft; must become a public 404.
        target = self.rng.choice(items)
        res = self.client.save_item({"asset_id": target["asset_id"],
                                     "website_status": "draft"})
        probe = self.client.item(target["asset_id"])
        total_ms = res.latency_ms + probe.latency_ms
        if res.ok and probe.status == 404:
            self._record(cenario, "despublicar", target["asset_id"], "ok", total_ms,
                         "published -> draft; public 404", invariantes=self._suite())
        else:
            self._record(cenario, "despublicar", target["asset_id"], "falha", total_ms,
                         f"patch HTTP {res.status}; public probe HTTP {probe.status}")

        # 2. undo: no endpoint (known gap) — the persona falls back to a manual
        #    patch restoring the previous value and logs that as the workaround.
        res = self.client.request("POST", "/undo", auth=True, json={})
        self._gap(cenario, "desfazer", "/undo", "gap-undo-endpoint", res)
        restore = self.client.save_item({"asset_id": target["asset_id"],
                                         "website_status": "published"})
        if restore.ok:
            self._record(cenario, "desfazer-manual", target["asset_id"], "ok",
                         restore.latency_ms, "manual patch restored website_status=published")

        # 3. request a new module: no channel (known gap).
        res = self.client.request("POST", "/modules/requests", auth=True,
                                  json={"module": "ticketing"})
        self._gap(cenario, "pedir-modulo", "/modules/requests", "gap-module-request-channel", res)
        return self.events


ROUTINES = {"diaria": "daily", "semanal": "weekly", "pontual": "punctual"}

# Routine scopes per persona email (team@demo is narrower until roles exist).
SCOPES = {
    "owner@demo": ["diaria", "semanal", "pontual"],
    "team@demo": ["diaria"],
}


def make_personas(client: ApiClient, seed: int, run_id: str,
                  museum_tier: str) -> list[Persona]:
    return [
        Persona(email, client, random.Random(f"{seed}:{email}"), run_id, museum_tier)
        for email in SCOPES
    ]

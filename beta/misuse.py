"""M3.2 — misuse generator: hostile scenarios against the serve API
(10 original + 2 assistant anti-abuse scenarios from M4.2).

Each scenario has an explicit expected outcome (accept gracefully or reject
with a useful error — never corrupt state, never lose data). Three verdicts:

- "passa"      — the product behaved as expected;
- "falha"      — behavior diverged: a genuine bug, goes to the known-bug list;
- "achado-gap" — the API cannot express the scenario at all (gap finding).

Red line (exit criterion of the phase): no scenario may cause data loss.
`snapshot_public_items` before/after proves the pre-existing collection is
byte-identical after the whole barrage.
"""

from __future__ import annotations

import json
import random
import string
import threading
import time
from dataclasses import dataclass

from .client import ApiClient
from .personas import Event, KNOWN_GAPS
from . import invariants as inv

# Additional gap surfaced by the misuse scenarios (beyond the persona gaps).
KNOWN_GAPS.setdefault(
    "gap-entitlement-change-via-api",
    "no API path to change the museum entitlement tier — it lives in museum.config.json, reloaded at serve boot",
)


def _slug(rng: random.Random, prefix: str) -> str:
    suffix = "".join(rng.choices(string.ascii_lowercase + string.digits, k=6))
    return f"beta-misuse-{prefix}-{suffix}"


def snapshot_public_items(client: ApiClient) -> dict[str, str]:
    """asset_id -> canonical JSON of every publicly served item."""
    snap: dict[str, str] = {}
    cols = client.collections().body["data"]
    for c in cols:
        res = client.collection_items(c["id"])
        if res.ok:
            for item in res.body["data"]:
                snap[item["asset_id"]] = json.dumps(item, sort_keys=True, ensure_ascii=False)
    return snap


class MisuseRunner:
    def __init__(self, client: ApiClient, rng: random.Random, run_id: str,
                 museum_tier: str):
        self.client = client
        self.rng = rng
        self.run_id = run_id
        self.museum_tier = museum_tier
        self.events: list[Event] = []
        from datetime import datetime, timezone
        self._now = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _record(self, cenario: str, acao: str, alvo: str, resultado: str,
                latencia_ms: float, detalhe: str = "",
                invariantes: list | None = None) -> Event:
        invs = invariantes or []
        veredito = "reprova" if (resultado == "falha" or any(not i.ok for i in invs)) else "passa"
        ev = Event(self.run_id, self._now(), cenario, "misuse@demo", acao, alvo,
                   resultado, latencia_ms, [i.as_dict() for i in invs], veredito, detalhe)
        self.events.append(ev)
        return ev

    def _suite(self) -> list:
        return inv.standard_suite(self.client, self.museum_tier)

    def _make_item(self, **over) -> dict:
        asset_id = _slug(self.rng, "item")
        col = self.client.collections().body["data"][0]["id"]
        card = {
            "asset_id": asset_id,
            "titulo": f"Item hostil {asset_id}",
            "colecao": col,
            "autor": "Gerador de Uso Indevido",
            "data": "2026",
            "material": "Digital",
            "descricao": "Criado pelo gerador de uso indevido do M3.2.",
            "tags": ["beta", "misuse"],
        }
        card.update(over)
        return card

    # -- the 10 scenarios (HANDOFF §M3 item 2) ----------------------------

    def s01_arquivo_grande(self) -> None:
        """Oversized file upload -> rejection with the declared limit."""
        res = self.client.request("POST", "/assets", auth=True,
                                  json={"filename": "huge.tif",
                                        "size": 500 * 1024 * 1024})
        if res.status in (404, 405):
            self._record("arquivo-grande", "upload-oversized", "/assets",
                         "achado-gap", res.latency_ms,
                         f"gap-upload-endpoint: {KNOWN_GAPS['gap-upload-endpoint']} (HTTP {res.status})")
        else:
            ok = res.status in (400, 413, 422)
            self._record("arquivo-grande", "upload-oversized", "/assets",
                         "ok" if ok else "falha", res.latency_ms,
                         f"HTTP {res.status} (expected a 4xx naming the size limit)",
                         invariantes=self._suite())

    def s02_mime_errado(self) -> None:
        """Wrong MIME type -> rejected at validation, nothing stored."""
        res = self.client.request("POST", "/assets", auth=True,
                                  json={"filename": "virus.exe",
                                        "content_type": "application/x-msdownload"})
        if res.status in (404, 405):
            self._record("mime-errado", "upload-wrong-mime", "/assets",
                         "achado-gap", res.latency_ms,
                         f"gap-upload-endpoint: {KNOWN_GAPS['gap-upload-endpoint']} (HTTP {res.status})")
        else:
            ok = res.status in (400, 415, 422)
            self._record("mime-errado", "upload-wrong-mime", "/assets",
                         "ok" if ok else "falha", res.latency_ms,
                         f"HTTP {res.status}", invariantes=self._suite())

    def s03_campo_obrigatorio_ausente(self) -> None:
        """Missing required field -> 422 naming the field."""
        card = self._make_item()
        del card["titulo"]
        res = self.client.save_item(card)
        body = json.dumps(res.body, ensure_ascii=False) if res.body else ""
        if res.status == 422 and "titulo" in body:
            self._record("campo-obrigatorio-ausente", "create-sem-titulo",
                         card["asset_id"], "ok", res.latency_ms,
                         "422 naming 'titulo'", invariantes=self._suite())
        elif res.status == 422:
            self._record("campo-obrigatorio-ausente", "create-sem-titulo",
                         card["asset_id"], "falha", res.latency_ms,
                         f"422 but message does not name the field: {body[:200]}")
        else:
            self._record("campo-obrigatorio-ausente", "create-sem-titulo",
                         card["asset_id"], "falha", res.latency_ms,
                         f"expected 422, got HTTP {res.status} — invalid card accepted?",
                         invariantes=self._suite())

    def s04_asset_id_duplicado(self) -> None:
        """Duplicate asset_id on create -> conflict; never silent overwrite."""
        card = self._make_item()
        r1 = self.client.save_item(card)
        dup = dict(card, titulo="TITULO SUBSTITUIDO PELO DUP", descricao="dup")
        r2 = self.client.save_item(dup)
        after = self.client.item(card["asset_id"], auth=True)
        kept = after.ok and after.body["data"].get("titulo") == card["titulo"]
        total = r1.latency_ms + r2.latency_ms + after.latency_ms
        if r2.status == 409 and kept:
            self._record("asset-id-duplicado", "create-duplicado", card["asset_id"],
                         "ok", total, "409 conflict; original intact",
                         invariantes=self._suite())
        elif r2.ok and not kept:
            self._record("asset-id-duplicado", "create-duplicado", card["asset_id"],
                         "falha", total,
                         "duplicate create SILENTLY PATCHED the existing card "
                         "(save_item patches when asset_id exists) — titulo overwritten",
                         invariantes=self._suite())
        else:
            self._record("asset-id-duplicado", "create-duplicado", card["asset_id"],
                         "falha", total,
                         f"unexpected: HTTP {r2.status}, original intact={kept}",
                         invariantes=self._suite())

    def s05_data_invalida(self) -> None:
        """Date handling, two halves (contract 1.1.0):
        - `data` is free display text by design (museum reality: "17th
          century", "1801-1900") — arbitrary text is ACCEPTED;
        - `data_iso` is the structured companion — garbage there is a 422.
        """
        card = self._make_item(data="banana-com-ouro")
        r1 = self.client.save_item(card)
        bad_iso = self._make_item(data_iso="banana-com-ouro")
        r2 = self.client.save_item(bad_iso)
        good_iso = self._make_item(data_iso="1665")
        r3 = self.client.save_item(good_iso)
        total = r1.latency_ms + r2.latency_ms + r3.latency_ms
        if r1.ok and r2.status == 422 and r3.ok:
            self._record("data-invalida", "create-data-livre-e-iso", card["asset_id"],
                         "ok", total,
                         "free-text data accepted by design; data_iso='banana-com-ouro' "
                         "rejected 422; data_iso='1665' accepted",
                         invariantes=self._suite())
        else:
            self._record("data-invalida", "create-data-livre-e-iso", card["asset_id"],
                         "falha", total,
                         f"data free-text HTTP {r1.status} (want 200); "
                         f"data_iso garbage HTTP {r2.status} (want 422); "
                         f"data_iso valid HTTP {r3.status} (want 200)",
                         invariantes=self._suite())

    def s06_glb_corrompido(self) -> None:
        """Corrupted .glb -> rejection; no half-written record."""
        res = self.client.request("POST", "/assets", auth=True,
                                  json={"filename": "broken.glb",
                                        "content": "not-a-glb"})
        if res.status in (404, 405):
            self._record("glb-corrompido", "upload-corrupted-glb", "/assets",
                         "achado-gap", res.latency_ms,
                         f"gap-upload-endpoint: {KNOWN_GAPS['gap-upload-endpoint']} (HTTP {res.status})")
        else:
            ok = res.status in (400, 415, 422)
            self._record("glb-corrompido", "upload-corrupted-glb", "/assets",
                         "ok" if ok else "falha", res.latency_ms,
                         f"HTTP {res.status}", invariantes=self._suite())

    def s07_upload_interrompido(self) -> None:
        """Interrupted upload -> consistent state, resume or rollback."""
        res = self.client.request("POST", "/assets", auth=True,
                                  json={"filename": "partial.jpg",
                                        "simulate": "connection-drop"})
        if res.status in (404, 405):
            self._record("upload-interrompido", "upload-drop", "/assets",
                         "achado-gap", res.latency_ms,
                         f"gap-upload-endpoint: {KNOWN_GAPS['gap-upload-endpoint']} (HTTP {res.status})")
        else:
            self._record("upload-interrompido", "upload-drop", "/assets",
                         "ok", res.latency_ms, f"HTTP {res.status}",
                         invariantes=self._suite())

    def s08_edicoes_concorrentes(self) -> None:
        """Two sessions patch the same card at once -> conflict or defined
        merge; never silent loss.

        With _rev (contract of the fixed API): both writers read, both patch
        with the _rev they read; exactly one wins, the other gets 409.
        Patches WITHOUT _rev are documented last-write-wins — tested too:
        they must at least not crash (the pre-fix race returned 500).
        """
        card = self._make_item()
        self.client.save_item(card)
        asset_id = card["asset_id"]
        read = self.client.item(asset_id, auth=True)
        rev = read.body["data"].get("_rev", 0)

        results: dict[str, int] = {}

        def patch(tag: str, with_rev: bool) -> None:
            c = ApiClient(self.client.base_url)
            c.token = self.client.token
            body = {"asset_id": asset_id, "descricao": f"escrita-{tag}"}
            if with_rev:
                body["_rev"] = rev
            res = c.save_item(body)
            results[tag] = res.status

        t1 = threading.Thread(target=patch, args=("A", True))
        t2 = threading.Thread(target=patch, args=("B", True))
        t1.start(); t2.start(); t1.join(); t2.join()
        codes = sorted(results.values())
        if codes == [200, 409]:
            self._record("edicoes-concorrentes", "patch-com-rev", asset_id,
                         "ok", 0.0,
                         f"optimistic concurrency: one writer 200, the other 409 "
                         f"(stale _rev) — no crash, no silent loss",
                         invariantes=self._suite())
        else:
            self._record("edicoes-concorrentes", "patch-com-rev", asset_id,
                         "falha", 0.0,
                         f"expected [200, 409], got {codes}",
                         invariantes=self._suite())

        # Without _rev: last-write-wins by design, but must never crash.
        t1 = threading.Thread(target=patch, args=("C", False))
        t2 = threading.Thread(target=patch, args=("D", False))
        t1.start(); t2.start(); t1.join(); t2.join()
        codes = sorted(results[k] for k in ("C", "D"))
        if codes == [200, 200]:
            self._record("edicoes-concorrentes", "patch-sem-rev", asset_id,
                         "ok", 0.0, "both 200, serialized — last-write-wins "
                         "by design, documented", invariantes=self._suite())
        else:
            self._record("edicoes-concorrentes", "patch-sem-rev", asset_id,
                         "falha", 0.0,
                         f"rev-less concurrent patches must serialize to [200, 200], "
                         f"got {codes} (the pre-fix race returned 500)",
                         invariantes=self._suite())

    def s09_token_invalido(self) -> None:
        """Expired/wrong token -> 401/403, no write, public unchanged."""
        before = snapshot_public_items(self.client)
        evil = ApiClient(self.client.base_url)
        evil.token = "token-forjado-000"
        res = evil.save_item(self._make_item())
        login = evil.request("POST", "/auth/login",
                             json={"email": "mallory@evil.example", "password": "wrong"})
        after = snapshot_public_items(self.client)
        unchanged = before == after
        if res.status in (401, 403) and login.status == 401 and unchanged:
            self._record("token-invalido", "write-com-token-forjado", "/items",
                         "ok", res.latency_ms,
                         "401 on write and login; public payload unchanged",
                         invariantes=self._suite())
        else:
            self._record("token-invalido", "write-com-token-forjado", "/items",
                         "falha", res.latency_ms,
                         f"write HTTP {res.status}; login HTTP {login.status}; "
                         f"public unchanged={unchanged}",
                         invariantes=self._suite())

    def s10_downgrade_tier(self) -> None:
        """Tier downgrade mid-way -> above-tier content leaves the payload;
        comes back intact on upgrade.

        Museum-level entitlement change has no API path (gap); what IS
        exercisable is the gate itself: an item whose tier is raised above
        the entitlement must vanish publicly and return intact when restored.
        """
        res = self.client.request("POST", "/entitlements", auth=True,
                                  json={"tier": "bronze"})
        if res.status in (404, 405):
            self._record("downgrade-tier", "mudar-entitlement", "/entitlements",
                         "achado-gap", res.latency_ms,
                         f"gap-entitlement-change-via-api: "
                         f"{KNOWN_GAPS['gap-entitlement-change-via-api']} (HTTP {res.status})")

        card = self._make_item()
        self.client.save_item(card)
        self.client.save_item({"asset_id": card["asset_id"], "website_status": "published"})
        above = "gold" if self.museum_tier != "gold" else "silver"
        # On a gold museum nothing is above tier; emulate with an unknown tier,
        # which fails closed (above any entitlement).
        if self.museum_tier == "gold":
            above = "platinum"
        r1 = self.client.save_item({"asset_id": card["asset_id"], "tier": above})
        probe_off = self.client.item(card["asset_id"])  # public
        r2 = self.client.save_item({"asset_id": card["asset_id"], "tier": "bronze"})
        probe_on = self.client.item(card["asset_id"])
        total = r1.latency_ms + r2.latency_ms + probe_off.latency_ms + probe_on.latency_ms
        if probe_off.status == 404 and probe_on.ok:
            self._record("downgrade-tier", "gate-no-downgrade", card["asset_id"],
                         "ok", total,
                         f"tier {above} -> public 404; restored -> visible again",
                         invariantes=self._suite())
        else:
            self._record("downgrade-tier", "gate-no-downgrade", card["asset_id"],
                         "falha", total,
                         f"above-tier public HTTP {probe_off.status} (want 404); "
                         f"restored public HTTP {probe_on.status} (want 200)",
                         invariantes=self._suite())

    def s11_pergunta_off_topic(self) -> None:
        """Off-topic question -> grounded refusal, zero provider cost, no crash.

        The unit tests (builder/tests/test_assistant.py) prove the refusal
        never reaches the LLM; here we prove the endpoint holds up through
        the real HTTP path with the fake provider wired (MUSA_LLM_FAKE=1).
        """
        res = self.client.request(
            "POST", "/assistant/ask",
            json={"question": "quem ganhou o campeonato de futebol xyzqw zzz?"})
        answer = (res.body or {}).get("answer", "")
        refused = "Só consigo responder" in answer
        if res.status == 200 and refused:
            self._record("pergunta-off-topic", "ask-off-topic", "/assistant/ask",
                         "ok", res.latency_ms,
                         "200 with the canned refusal — no provider call, no crash",
                         invariantes=self._suite())
        else:
            self._record("pergunta-off-topic", "ask-off-topic", "/assistant/ask",
                         "falha", res.latency_ms,
                         f"expected 200 + canned refusal, got HTTP {res.status}: "
                         f"{str(res.body)[:160]}",
                         invariantes=self._suite())

    def s12_bot_martelando_chat(self) -> None:
        """Bot hammering the assistant -> 429s appear, service survives.

        Runs LAST in the barrage on purpose: the per-IP window it fills must
        not interfere with the other scenarios. 15 asks against a 10/min
        limit must yield a mix of 200 and 429 — nothing else — and /health
        must stay green afterwards.
        """
        cols = self.client.collections().body["data"]
        items = self.client.collection_items(cols[0]["id"]).body["data"]
        title = items[0].get("titulo") or items[0]["asset_id"]
        codes: list[int] = []
        t0 = time.perf_counter()
        for _ in range(15):
            res = self.client.request("POST", "/assistant/ask",
                                      json={"question": f"me fale sobre {title}"})
            codes.append(res.status)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        health = self.client.health(timeout=1.5)
        ok = (200 in codes and 429 in codes
              and all(c in (200, 429) for c in codes) and health.ok)
        self._record("bot-martelando-chat", "flood-assistant", "/assistant/ask",
                     "ok" if ok else "falha", elapsed_ms,
                     f"15 asks -> {sorted(set(codes))} "
                     f"({codes.count(429)}x 429); health after: {health.status}",
                     invariantes=self._suite())

    SCENARIOS = [
        ("01-arquivo-grande", s01_arquivo_grande),
        ("02-mime-errado", s02_mime_errado),
        ("03-campo-obrigatorio-ausente", s03_campo_obrigatorio_ausente),
        ("04-asset-id-duplicado", s04_asset_id_duplicado),
        ("05-data-invalida", s05_data_invalida),
        ("06-glb-corrompido", s06_glb_corrompido),
        ("07-upload-interrompido", s07_upload_interrompido),
        ("08-edicoes-concorrentes", s08_edicoes_concorrentes),
        ("09-token-invalido", s09_token_invalido),
        ("10-downgrade-tier", s10_downgrade_tier),
        ("11-pergunta-off-topic", s11_pergunta_off_topic),
        ("12-bot-martelando-chat", s12_bot_martelando_chat),
    ]

    def run_all(self) -> list[Event]:
        before = snapshot_public_items(self.client)
        for _name, fn in self.SCENARIOS:
            fn(self)
        after = snapshot_public_items(self.client)
        lost = [aid for aid, payload in before.items()
                if aid not in after or after[aid] != payload]
        if lost:
            self._record("linha-vermelha", "perda-de-dados", ",".join(lost[:5]),
                         "falha", 0.0,
                         f"RED LINE CROSSED: {len(lost)} pre-existing public item(s) "
                         f"lost or changed by the misuse barrage")
        else:
            self._record("linha-vermelha", "perda-de-dados", "-", "ok", 0.0,
                         f"{len(before)} pre-existing public items byte-identical "
                         f"after all scenarios")
        return self.events

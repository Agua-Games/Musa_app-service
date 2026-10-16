"""M4.3 — gating audit as a contract-attachable artifact.

Proves, with plain-language Portuguese output a non-technical reader can
follow, that the content gate holds for one museum: no draft and no
above-tier record reaches the public — not its JSON, not its files, not a
search hit. This is a test, not a promise (HANDOFF §M4).

The audit boots the real serve app in-process (TestClient — no ports, no
network) against a throwaway overlay and probes the exact HTTP paths the
public site uses, plus the positive control: the same probes WITH the admin
token must see drafts (so a 404 is a gate decision, not missing data) and
must STILL not see above-tier records (tier never relaxes, M1.4).

Run:  python -m musa_build audit --repo <repo> [--out auditoria.md]
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import CONTRACT_VERSION, __version__
from .build import _is_url
from .contract import make_validator, validate_card
from .gate import TIER_ORDER

AUDIT_TOKEN = "audit-positive-control-token"


@dataclass
class AuditCheck:
    key: str
    titulo: str
    sondas: int = 0
    vazamentos: list[str] = field(default_factory=list)
    detalhe: str = ""

    @property
    def ok(self) -> bool:
        return not self.vazamentos


@dataclass
class GatingAudit:
    museum_id: str
    tier: str
    date: str
    builder_version: str
    contract_version: str
    total_items: int
    public_items: int
    draft_items: int
    above_tier_items: int
    above_tier_collections: int
    checks: list[AuditCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def probes(self) -> int:
        return sum(c.sondas for c in self.checks)


def _asset_probes(item: dict) -> list[str]:
    """Local asset paths of one ungated record, as URL fragments the public
    site would use. Only files that actually exist in the repo are probed."""
    item_dir = item.get("_dir")
    if item_dir is None:
        return []
    paths = []
    for key in ("image", "model_primary"):
        value = item.get(key)
        if value and not _is_url(value) and (item_dir / value).is_file():
            paths.append(f"/assets/content/{item['colecao']}/{item['asset_id']}/{value}")
    return paths


def run_gating_audit(repo: Path) -> GatingAudit:
    """Boot the real app on the repository and probe the public HTTP surface."""
    from fastapi.testclient import TestClient

    from .serve import create_app

    tmp = tempfile.TemporaryDirectory()
    old_token = os.environ.get("MUSA_ADMIN_TOKEN")
    os.environ["MUSA_ADMIN_TOKEN"] = AUDIT_TOKEN
    try:
        app = create_app(Path(repo), data_dir=Path(tmp.name))
        try:
            client = TestClient(app)
            return _probe(client, app.state.serve)
        finally:
            app.state.serve.store.close()
    finally:
        if old_token is None:
            os.environ.pop("MUSA_ADMIN_TOKEN", None)
        else:
            os.environ["MUSA_ADMIN_TOKEN"] = old_token
        tmp.cleanup()


def _probe(client, state) -> GatingAudit:
    allowed = TIER_ORDER[state.tier]
    auth = {"Authorization": f"Bearer {AUDIT_TOKEN}"}

    drafts = [i for i in state.all_items if i.get("website_status") != "published"]
    above_items = [
        i for i in state.all_items
        if TIER_ORDER.get((i.get("tier") or "bronze").lower(), 99) > allowed
    ]
    above_collections = [
        c for c in state.all_collections
        if TIER_ORDER.get((c.get("tier") or "bronze").lower(), 99) > allowed
    ]

    audit = GatingAudit(
        museum_id=state.museum_id,
        tier=state.tier,
        date=datetime.now(timezone.utc).date().isoformat(),
        builder_version=__version__,
        contract_version=CONTRACT_VERSION,
        total_items=len(state.all_items),
        public_items=len(state.items),
        draft_items=len(drafts),
        above_tier_items=len(above_items),
        above_tier_collections=len(above_collections),
    )

    # 1. Every public item validates against the frozen contract.
    check = AuditCheck("contrato-valido", "Todo item público é válido pelo contrato do card")
    validator = make_validator()
    for item in state.items:
        check.sondas += 1
        problems = validate_card(item, validator)
        if problems:
            check.vazamentos.append(f"{item['asset_id']}: {'; '.join(problems)}")
    check.detalhe = f"{check.sondas} item(ns) público(s) validados um a um"
    audit.checks.append(check)

    # 2. No draft is publicly visible — neither its JSON nor its files.
    check = AuditCheck("rascunhos-invisiveis", "Nenhum rascunho aparece no público (JSON e arquivos)")
    for item in drafts:
        check.sondas += 1
        if client.get(f"/items/{item['asset_id']}").status_code != 404:
            check.vazamentos.append(f"{item['asset_id']}: JSON público não é 404")
        for path in _asset_probes(item):
            check.sondas += 1
            if client.get(path).status_code != 404:
                check.vazamentos.append(f"{item['asset_id']}: arquivo {path} não é 404")
    check.detalhe = f"{len(drafts)} rascunho(s), cada um sondado no JSON e em cada arquivo local"
    audit.checks.append(check)

    # 3. Nothing above the entitled tier leaks — records, files, collections.
    check = AuditCheck("nada-acima-do-tier",
                       f"Nada acima do tier contratado ({state.tier}) vaza")
    for item in above_items:
        check.sondas += 1
        if client.get(f"/items/{item['asset_id']}").status_code != 404:
            check.vazamentos.append(f"{item['asset_id']}: JSON público não é 404")
        for path in _asset_probes(item):
            check.sondas += 1
            if client.get(path).status_code != 404:
                check.vazamentos.append(f"{item['asset_id']}: arquivo {path} não é 404")
    listed = {c["id"] for c in client.get("/collections").json()["data"]}
    for collection in above_collections:
        check.sondas += 2
        if collection["id"] in listed:
            check.vazamentos.append(f"coleção {collection['id']}: listada publicamente")
        res = client.get(f"/collections/{collection['id']}/items")
        if res.status_code != 404:
            check.vazamentos.append(f"coleção {collection['id']}: /items não é 404")
    check.detalhe = (f"{len(above_items)} item(ns) e {len(above_collections)} "
                     f"coleção(ões) acima do tier, sondados em JSON e arquivos")
    audit.checks.append(check)

    # 4. Positive control: WITH the admin token, drafts ARE visible (the 404s
    # above are gate decisions, not missing data) — and above-tier records
    # stay invisible even for the admin (tier never relaxes).
    check = AuditCheck("controle-positivo",
                       "Controle positivo: admin vê rascunhos; tier nunca relaxa")
    for item in drafts:
        check.sondas += 1
        if client.get(f"/items/{item['asset_id']}", headers=auth).status_code != 200:
            check.vazamentos.append(
                f"{item['asset_id']}: rascunho invisível até para o admin — "
                "os 404s do público podem ser dado ausente, não decisão do portão")
    for item in above_items:
        check.sondas += 1
        if client.get(f"/items/{item['asset_id']}", headers=auth).status_code != 404:
            check.vazamentos.append(
                f"{item['asset_id']}: admin viu registro acima do tier — o portão relaxou")
    check.detalhe = ("cada rascunho re-sondado com token (deve aparecer) e cada "
                     "registro acima do tier re-sondado com token (deve sumir mesmo assim)")
    audit.checks.append(check)

    # 5. The search index only contains public records.
    check = AuditCheck("busca-limpa", "A busca pública não devolve registros excluídos")
    excluded = {i["asset_id"]: i for i in drafts + above_items}
    from .api import _tokenize
    for asset_id, item in excluded.items():
        tokens = sorted(_tokenize(str(item.get("titulo") or "")), key=len, reverse=True)
        if not tokens:
            continue
        check.sondas += 1
        res = client.get("/search", params={"q": tokens[0]})
        hits = {h["asset_id"] for h in res.json()["data"]}
        if asset_id in hits:
            check.vazamentos.append(f"{asset_id}: aparece na busca por {tokens[0]!r}")
    check.detalhe = "cada registro excluído pesquisado pelo token mais distintivo do título"
    audit.checks.append(check)

    # 6. Record descriptors and dotfiles are never downloadable assets.
    # (Probe the ungated records — state.items is shaped and loses _dir —
    # but only those that ARE public: an excluded record's card.json is
    # already covered by checks 2/3.)
    check = AuditCheck("arquivos-reservados",
                       "Descritores internos (card.json) e dotfiles não são baixáveis")
    for item in state.all_items:
        if (item.get("colecao"), item.get("asset_id")) not in state.included_items:
            continue
        item_dir = item.get("_dir")
        if item_dir is None or not (item_dir / "card.json").is_file():
            continue
        check.sondas += 1
        path = f"/assets/content/{item['colecao']}/{item['asset_id']}/card.json"
        if client.get(path).status_code != 404:
            check.vazamentos.append(f"{item['asset_id']}: {path} baixável")
    check.detalhe = "card.json de cada item público com diretório próprio, sondado"
    audit.checks.append(check)

    return audit


def render_markdown(audit: GatingAudit) -> str:
    """The contract-attachable report, in plain Portuguese."""
    lines: list[str] = []
    add = lines.append
    add(f"# Auditoria de gating — {audit.museum_id}")
    add("")
    add(f"> Gerado por `musa-build audit` em {audit.date} · plataforma "
        f"v{audit.builder_version} · contrato do card v{audit.contract_version}. "
        "Documento gerado por teste automatizado — não editado à mão.")
    add("")
    add("## O que este relatório prova")
    add("")
    add(f"O museu **{audit.museum_id}** tem contrato de tier **{audit.tier}**. "
        "O portão de conteúdo (a regra que separa o que o público pode ver) foi "
        "testado de verdade, sonda a sonda, contra a API real:")
    add("")
    add(f"- **Rascunhos** ({audit.draft_items}): nenhum aparece no site público — "
        "nem o cadastro (JSON), nem as imagens/modelos 3D, nem na busca.")
    add(f"- **Acima do tier** ({audit.above_tier_items} item(ns) e "
        f"{audit.above_tier_collections} coleção(ões)): invisíveis para o público "
        "**e continuam invisíveis até com o token de administrador** — o tier "
        "contratado nunca relaxa.")
    if audit.above_tier_items == 0 and audit.above_tier_collections == 0:
        add("  - _Nenhum registro acima do tier existe neste acervo (esperado no "
            "gold, o tier máximo): esta verificação é vacuamente verdadeira aqui. "
            "O caminho é exercido de verdade na suíte da plataforma "
            "(`builder/tests/test_audit.py`, fixture silver com registro gold)._")
    add("- **Controle positivo**: com o token de administrador os rascunhos "
        "aparecem — ou seja, os 404 do público são decisão do portão, não dado "
        "faltando.")
    add("- **Contrato**: todo item público é válido pelo contrato congelado do card.")
    add("")
    veredito = ("**APROVADO** ✔" if audit.ok else "**REPROVADO** ✘ — vazamentos abaixo")
    add(f"## Resultado: {veredito}")
    add("")
    add(f"{len(audit.checks)} verificações, {audit.probes} sondas HTTP no total.")
    add("")
    add("| Verificação | Sondas | Resultado |")
    add("|---|---|---|")
    for check in audit.checks:
        marca = "✔" if check.ok else "✘"
        add(f"| {check.titulo} | {check.sondas} | {marca} |")
    add("")
    add("## Detalhes por verificação")
    add("")
    for check in audit.checks:
        add(f"### {check.titulo}")
        add("")
        add(check.detalhe + ".")
        add("")
        if check.vazamentos:
            add("**Vazamentos encontrados:**")
            add("")
            for leak in check.vazamentos[:20]:
                add(f"- {leak}")
            add("")
    add("## Inventário")
    add("")
    add(f"- Itens no repositório: {audit.total_items}")
    add(f"- Públicos (publicados e dentro do tier): {audit.public_items}")
    add(f"- Rascunhos (excluídos do público): {audit.draft_items}")
    add(f"- Acima do tier {audit.tier} (excluídos do público): {audit.above_tier_items} "
        f"item(ns), {audit.above_tier_collections} coleção(ões)")
    add("")
    add("## Como reproduzir")
    add("")
    add("```bash")
    add("cd builder && python -m musa_build audit --repo <repositório do museu> --out auditoria.md")
    add("```")
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="musa-build audit",
        description="Gating audit (M4.3): proves, probe by probe, that no draft "
                    "and no above-tier record reaches the public — and renders a "
                    "plain-Portuguese report attachable to a contract.",
    )
    parser.add_argument("--repo", required=True, help="client repository root")
    parser.add_argument("--out", default=None,
                        help="write the markdown report here (default: print a summary only)")
    args = parser.parse_args(argv)

    audit = run_gating_audit(Path(args.repo))
    status = "APROVADO" if audit.ok else "REPROVADO"
    print(f"AUDIT {status} — {audit.museum_id} (tier {audit.tier}): "
          f"{len(audit.checks)} verificações, {audit.probes} sondas, "
          f"{audit.draft_items} rascunhos e {audit.above_tier_items} acima-do-tier invisíveis")
    for check in audit.checks:
        marca = "OK " if check.ok else "FALHA"
        print(f"  [{marca}] {check.titulo} ({check.sondas} sondas)")
        for leak in check.vazamentos[:5]:
            print(f"        vazamento: {leak}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(audit), encoding="utf-8", newline="\n")
        print(f"relatório: {out}")
    return 0 if audit.ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

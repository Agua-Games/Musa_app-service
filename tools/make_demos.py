"""M4.7 — generate the three fictional demo museums (one per tier), local-first.

The demos are CLIENT REPOSITORIES (ADR 0003: content + config, zero MUSA
code), created as siblings of the platform repo under ``<parent>/demos/`` —
the same place the DemoMuseum lives. They are signed with the real platform
key (the genuine onboarding flow), they build with the local builder, and
they stay local until the owner decides to push them to GitHub (public repos
cost nothing: unlimited repos, free Actions on public).

Assets: cards reference the DemoMuseum's already-uploaded R2 URLs (zero new
transfers), except one small GLB copied into the silver demo so its 3D piece
works fully offline. No network, no uploads.

Usage (from the platform repo root):

    python tools/make_demos.py --parent H:\\Musa_app-service \\
        --key H:\\Musa_app-service\\secrets\\musa-entitlements-ed25519.key
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

PLATFORM_ROOT = Path(__file__).resolve().parent.parent

R2 = "https://pub-61e9fc2b46a54c66a9421fe7c23a5b64.r2.dev"

GITIGNORE = ".musa/\n_site/\n__pycache__/\n"

README = """# {title} — MUSA demo museum ({tier})

Fictional demonstration museum, tier **{tier}** (M4.7). Content + config only —
the MUSA runtime is the pinned artifact (`musa` in museum.config.json).

Local-first: builds and serves with the platform's local builder. To publish:
apply the client template CI (see docs/runbook.md §Onboarding in the platform
repo) and enable Pages. Modules: {modules}.
"""

# Institutional pages (the builder's static-pages feature, musa-app >= 0.6.0):
# every demo ships privacidade + termos so the footer is complete out of the box.
_PRIVACIDADE = """---
titulo: Política de Privacidade
ordem: 1
---

# Política de Privacidade — {name}

> O **{name}** é um museu fictício de demonstração da plataforma MUSA.

**Controlador:** {name} (museu fictício), CNPJ 00.000.000/0001-00
**Operador da plataforma:** Agua-Games (plataforma MUSA)
**Última atualização:** 2026-10-17

## 1. O que coletamos

**Quase nada — por desenho.** Todo o acervo é visitável sem conta, sem
cookies e sem analytics. GitHub Pages e Cloudflare mantêm logs técnicos
próprios (como IP), sob as políticas deles.

## 2. Assistente de acervo (quando disponível)

A pergunta é processada pelo provedor de IA (DeepSeek) **sem nenhum dado
que identifique você**, e não fica gravada em logs. O IP é usado só em
memória, para limitar abusos, de forma pseudonimizada.

## 3. Seus direitos (LGPD)

Como não mantemos dados identificáveis de visitantes, provavelmente **não
há dados seus para exportar ou eliminar** — mas solicitações (art. 18 da
LGPD) são sempre respondidas: privacidade@{domain}.

## 4. Acervo, créditos e licenças

Cada peça informa sua **licença e fonte** na própria ficha — essa é a
informação que vale para reutilização.
"""

_TERMOS = """---
titulo: Termos de Uso
ordem: 2
---

# Termos de Uso — {name}

> O **{name}** é um museu fictício de demonstração da plataforma MUSA.

**Última atualização:** 2026-10-17

## 1. Uso do site

Visitação **livre e sem cadastro**. Permitido: consulta e compartilhamento
de links para fins pessoais, educacionais e não comerciais.

## 2. Direitos autorais

As fichas e imagens pertencem ao Museu ou a terceiros licenciantes. **Cada
peça informa licença e fonte na ficha** — obras CC0/domínio público seguem
a licença indicada, não este parágrafo. Não é permitido scraping em massa
nem uso comercial sem licença.

## 3. Conduta

Sem requisições automatizadas abusivas (há limite por minuto), sem uso do
assistente para fins alheios ao acervo, sem burlar a verificação anti-robô.

## 4. Assistente virtual (IA)

Pode errar: respostas são informativas e a **ficha da peça é a fonte
autoritativa**.

## 5. Disposições gerais

Legislação brasileira. O site é oferecido "como está", sem exclusão de
direitos irrenunciáveis do consumidor (CDC). Privacidade: ver
[Política de Privacidade](privacidade.html). Contato: contato@{domain}.
"""


def _write_pages(repo: Path, name: str, domain: str) -> None:
    paginas = repo / "content" / "paginas"
    paginas.mkdir(parents=True, exist_ok=True)
    (paginas / "privacidade.md").write_text(
        _PRIVACIDADE.format(name=name, domain=domain), encoding="utf-8")
    (paginas / "termos.md").write_text(
        _TERMOS.format(name=name, domain=domain), encoding="utf-8")


def _card(asset_id: str, colecao: str, titulo: str, autor: str, tier: str,
          image: str | None = None, **extra) -> dict:
    card = {
        "asset_id": asset_id,
        "colecao": colecao,
        "titulo": titulo,
        "autor": autor,
        "website_status": "published",
        "tier": tier,
        "licenca": "Domínio público",
        "fonte": "Wikimedia Commons",
    }
    if image:
        card["image"] = image
    card.update(extra)
    return {k: v for k, v in card.items() if v is not None}


def _write_item(repo: Path, card: dict, extra_files: dict[str, Path] | None = None) -> None:
    item_dir = repo / "content" / card["colecao"] / card["asset_id"]
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "card.json").write_text(
        json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, source in (extra_files or {}).items():
        target = item_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _config(museum_id: str, name: str, tagline: str, tier: str, modules: list[str],
            skin: dict | None = None) -> dict:
    return {
        "museum": {"id": museum_id, "name": name, "tagline": tagline,
                   "locale": "pt-BR", "domain": f"{museum_id}.musa.example"},
        "musa": "0.6.0",
        "entitlements": {
            "tier": tier,
            "modules": modules,
            "issued": date.today().isoformat(),
            "expires": "2030-12-31",
            "museum_id": museum_id,
        },
        "storage": {"provider": "none", "assetsBaseUrl": ""},
        "site": {"skin": skin or {}},
    }


def make_bronze(demos: Path) -> Path:
    repo = demos / "atelier-bronze"
    (repo / "content").mkdir(parents=True, exist_ok=True)
    _write_item(repo, _card(
        "a-leiteira", "pinturas", "A Leiteira", "Johannes Vermeer", "bronze",
        image=f"{R2}/pinturas/a-leiteira/images/a-leiteira.jpg",
        data="c. 1657–1658", data_iso="1658", material="Óleo sobre tela",
        descricao="A quietude doméstica de Delft em uma janela de luz."))
    _write_item(repo, _card(
        "moca-com-brinco-de-perola", "pinturas", "Moça com Brinco de Pérola",
        "Johannes Vermeer", "bronze",
        image=f"{R2}/pinturas/moca-com-brinco-de-perola/images/moca-com-brinco-de-perola.jpg",
        data="c. 1665", data_iso="1665", material="Óleo sobre tela"))
    _write_item(repo, _card(
        "nenufares", "pinturas", "Nenúfares", "Claude Monet", "bronze",
        image=f"{R2}/pinturas/nenufares/images/nenufares.jpg",
        data="1906", data_iso="1906", material="Óleo sobre tela"))
    _write_item(repo, _card(
        "ronda-noturna", "pinturas", "A Ronda Noturna", "Rembrandt van Rijn", "bronze",
        image=f"{R2}/pinturas/ronda-noturna/images/ronda-noturna.jpg",
        data="1642", data_iso="1642", material="Óleo sobre tela"))
    (repo / "museum.config.json").write_text(json.dumps(
        _config("atelier-bronze", "Atelier da Encosta", "Quatro séculos de pintura, na parede da sua tela.",
                "bronze", []), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return repo


def make_silver(demos: Path, models: Path) -> Path:
    repo = demos / "galeria-silver"
    (repo / "content").mkdir(parents=True, exist_ok=True)
    _write_item(repo, _card(
        "autorretrato-van-gogh", "pinturas", "Autorretrato", "Vincent van Gogh", "bronze",
        image=f"{R2}/pinturas/autorretrato-van-gogh/images/autorretrato-van-gogh.jpg",
        data="1889", data_iso="1889", material="Óleo sobre tela"))
    _write_item(repo, _card(
        "nenufares", "pinturas", "Nenúfares", "Claude Monet", "bronze",
        image=f"{R2}/pinturas/nenufares/images/nenufares.jpg",
        data="1906", data_iso="1906", material="Óleo sobre tela"))
    # The hero 3D piece: a LOCAL model so the demo works fully offline.
    _write_item(repo, _card(
        "venus-de-milo", "esculturas", "Vênus de Milo", "Alexandros de Antióquia", "silver",
        image=f"{R2}/esculturas/venus-de-milo/images/venus-de-milo.jpg",
        data="c. 150–125 a.C.", data_iso="-150", material="Mármore de Paros",
        model_primary="model.glb", model_formats=["glb"], model_viewer="three_js",
        model_status="available", licenca="CC0 1.0",
        fonte="Scan the World / domínio público"),
        {"model.glb": models / "venus-de-milo.glb"})
    (repo / "museum.config.json").write_text(json.dumps(
        _config("galeria-silver", "Galeria Prata-Viva", "Suas peças-herói, em 360 graus.",
                "silver", ["assistant"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return repo


def make_gold(demos: Path) -> Path:
    repo = demos / "palazzo-gold"
    (repo / "content").mkdir(parents=True, exist_ok=True)
    for asset_id, titulo, autor, data, data_iso, tier in (
        ("a-leiteira", "A Leiteira", "Johannes Vermeer", "c. 1657–1658", "1658", "bronze"),
        ("moca-com-brinco-de-perola", "Moça com Brinco de Pérola", "Johannes Vermeer", "c. 1665", "1665", "bronze"),
        ("nenufares", "Nenúfares", "Claude Monet", "1906", "1906", "bronze"),
        ("ronda-noturna", "A Ronda Noturna", "Rembrandt van Rijn", "1642", "1642", "silver"),
        ("autorretrato-van-gogh", "Autorretrato", "Vincent van Gogh", "1889", "1889", "silver"),
    ):
        colecao = "pinturas"
        _write_item(repo, _card(
            asset_id, colecao, titulo, autor, tier,
            image=f"{R2}/{colecao}/{asset_id}/images/{asset_id}.jpg",
            data=data, data_iso=data_iso, material="Óleo sobre tela"))
    _write_item(repo, _card(
        "anfora-figuras-negras", "esculturas", "Ânfora de Figuras Negras",
        "Desconhecido (oficina ática)", "gold",
        image=f"{R2}/esculturas/anfora-figuras-negras/images/anfora-figuras-negras.jpg",
        data="c. 530 a.C.", data_iso="-530", material="Terracota",
        licenca="CC0 1.0", fonte="The Metropolitan Museum of Art"))
    # Gold-only services: cinema programme + store products (content/site.json).
    (repo / "content" / "site.json").write_text(json.dumps({
        "films": [{
            "id": "a-ronda-restaurada",
            "title": "A Ronda Noturna — a restauração ao vivo",
            "year": 2024, "duration": "44 min",
            "synopsis": "A operação Night Watch do Rijksmuseum, em detalhe.",
            "credit": "Rijksmuseum (domínio público)",
            "screenings": ["sex 20h", "sáb 16h"],
        }],
        "products": [
            {"id": "ingresso", "name": "Ingresso — visite o Palazzo", "price": "R$ 30",
             "desc": "Acesso ao dia inteiro, todas as alas."},
            {"id": "poster-nenufares", "name": "Pôster — Nenúfares (1906)", "price": "R$ 80",
             "desc": "Impressão fine-art 50×70 cm, obra em domínio público."},
        ],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (repo / "museum.config.json").write_text(json.dumps(
        _config("palazzo-gold", "Palazzo Áureo", "O palácio inteiro, espelhado online.",
                "gold", ["assistant", "store", "streaming", "screening-room"]),
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return repo


def sign(repo: Path, key: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(PLATFORM_ROOT / "tools" / "sign_entitlements.py"),
         "sign", "--repo", str(repo), "--key", str(key)],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"signing failed for {repo}: {proc.stdout} {proc.stderr}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--parent", default=str(PLATFORM_ROOT.parent),
                        help="directory the demos/ folder is created in")
    parser.add_argument("--key", required=True, help="platform Ed25519 private key file")
    args = parser.parse_args(argv)

    key = Path(args.key)
    if not key.is_file():
        raise SystemExit(f"platform key not found at {key}")
    demos = Path(args.parent) / "demos"
    models = PLATFORM_ROOT / "source" / "assets" / "models"

    made = []
    for maker in (make_bronze, make_gold):
        made.append(maker(demos))
    made.append(make_silver(demos, models))
    for repo in made:
        (repo / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
        config = json.loads((repo / "museum.config.json").read_text(encoding="utf-8"))
        ent = config["entitlements"]
        _write_pages(repo, config["museum"]["name"], config["museum"]["domain"])
        (repo / "README.md").write_text(
            README.format(title=config["museum"]["name"], tier=ent["tier"],
                          modules=", ".join(ent["modules"]) or "nenhum"),
            encoding="utf-8")
        sign(repo, key)
        items = list(repo.glob("content/*/*/card.json"))
        print(f"OK {repo.name}: tier {ent['tier']}, modules {ent['modules']}, "
              f"{len(items)} items, entitlements signed")
    print(f"\nDemos at {demos}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

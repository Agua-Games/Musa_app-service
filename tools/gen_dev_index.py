"""Generate docs/dev-index.md — the always-fresh entry point for AI agents
(and new devs) working on the MUSA codebase.

The problem it solves: an agent (or a new teammate) that has to re-digest the
whole repo every session wastes tokens and time. This index is the curated
map — what each part is, where the entry points are, which suites prove what —
with the volatile parts (versions, counts, file listings) AUTO-GENERATED so
the file never lies by omission for long.

Regenerate after structural changes (new module, new tool, new suite):

    python tools/gen_dev_index.py          # writes docs/dev-index.md
    python tools/gen_dev_index.py --check  # exit 1 if stale (CI-friendly)

Point your agent's config at docs/dev-index.md (AGENTS.md already does).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "docs" / "dev-index.md"

sys.path.insert(0, str(ROOT / "builder"))
from musa_build import CONTRACT_VERSION, __version__  # noqa: E402

# Curated map — the didactic layer. One line per component, in the vocabulary
# a newcomer needs. Update this table when a component is born or dies.
COMPONENTS = [
    ("builder/musa_build/", "o motor: build do site estático + API dinâmica (serve) + gate do contrato",
     "cli.py, build.py, serve.py, gate.py, contract.py, entitlements.py, pages.py, api.py"),
    ("builder/musa_build/schemas/", "schema do card embutido no artefato (uma fonte de verdade, com teste de drift)",
     "card.schema.json"),
    ("source/", "o frontend (landing + acervo + viewers 3D + admin) — é também o template do site do cliente",
     "index.html, assets/js/main.js, assets/css/style.css"),
    ("pipeline/", "catalogação assistida por IA (M2): OCR → estruturação LLM → cards; venv próprio em pipeline/.venv",
     "README, build_vector_index.py"),
    ("mcp_server/", "servidor MCP stdio (8 ferramentas) — opera o acervo a partir de qualquer cliente MCP/agente",
     "server.py, tools.py"),
    ("beta/", "cliente virtual: personas, gerador de uso indevido, bateria de edge cases, harness de serve",
     "run_beta.py, personas.py, misuse.py, edge.py, harness.py, invariants.py"),
    ("tools/", "ferramentas de plataforma (uma por arquivo, com docstring de uso)",
     None),
    ("schemas/", "contrato do card versionado (fonte canônica; o builder embute uma cópia)",
     "card/v1/card.schema.json, COMPATIBILITY.md"),
    ("docs/", "documentação viva (HANDOFF, planos de milestone, ADRs, SLOs, runbook, modelos legais)",
     "HANDOFF.md, adr/"),
    (".github/workflows/", "CI da plataforma, release do artefato (tag v* → imagem no ghcr.io), Pages",
     "ci.yml, release.yml, pages.yml"),
]

SUITES = [
    ("builder/tests/", "cd builder && python -m unittest discover -s tests", "contrato, gate, build, serve, páginas, backup, alertas…"),
    ("mcp_server/tests/", "cd mcp_server && python -m unittest discover -s tests", "as 8 ferramentas + smoke do protocolo stdio"),
    ("beta/tests/", "python -m unittest discover -s beta/tests -t .", "harness, personas, misuse, edge battery"),
]


def _count(pattern: str, root: Path = ROOT) -> int:
    return sum(1 for p in root.glob(pattern) if p.is_file())


def _tools_listing() -> list[str]:
    import ast
    lines = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        first = ""
        try:
            doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
            if doc:
                first = doc.strip().splitlines()[0].rstrip(".")
        except (OSError, SyntaxError):
            pass
        lines.append(f"| `tools/{path.name}` | {first or '(sem docstring)'} |")
    return lines


def render() -> str:
    out: list[str] = []
    w = out.append
    w("<!--- GERADO por tools/gen_dev_index.py — não editar à mão; edite o gerador. -->")
    w("")
    w("# Dev index — mapa vivo do repositório MUSA")
    w("")
    w(f"> Gerado em máquina local · plataforma **v{__version__}** · contrato do card "
      f"**v{CONTRACT_VERSION}**. Ponto de entrada para agentes de IA e devs novos:")
    w("> leia este arquivo PRIMEIRO, depois `docs/arquitetura.md`. Referência de")
    w("> API: `docs/api-reference.md` (gerada). Comandos: `docs/comandos-dev.md`.")
    w("")
    w("## O sistema em um parágrafo")
    w("")
    w("MUSA é um app-service para museus: o cliente tem um **repositório de conteúdo**")
    w("(cards + assets + config — zero código nosso) e a plataforma distribui um")
    w("**artefato** (imagem de contêiner `ghcr.io/agua-games/musa-app:<versão>`) que")
    w("constrói e serve o site do museu. Tier e módulos vêm de **entitlements")
    w("assinados Ed25519**; o gate garante que draft e conteúdo acima do tier nunca")
    w("chegam ao payload publicado.")
    w("")
    w("## Componentes")
    w("")
    w("| Onde | O que é | Arquivos-chave |")
    w("|---|---|---|")
    for path, desc, keys in COMPONENTS:
        w(f"| `{path}` | {desc} | {keys or '—'} |")
    w("")
    w("## Suítes de teste (rodar antes de push)")
    w("")
    w("| Suíte | Comando | Cobre |")
    w("|---|---|---|")
    for suite, cmd, covers in SUITES:
        w(f"| `{suite}` | `{cmd}` | {covers} |")
    w("")
    w("## Ferramentas de plataforma (tools/)")
    w("")
    w("| Arquivo | O que faz |")
    w("|---|---|")
    out.extend(_tools_listing())
    w("")
    w("## Números atuais (auto-gerados)")
    w("")
    w(f"- Cards de schema: {_count('schemas/**/*.json')} · ADRs: {_count('docs/adr/*.md')} "
      f"· docs: {_count('docs/*.md')} na raiz de docs/")
    w(f"- Testes: {_count('builder/tests/test_*.py')} arquivos no builder, "
      f"{_count('mcp_server/tests/test_*.py')} no MCP server, {_count('beta/tests/test_*.py')} no beta")
    w("")
    w("## Para onde ir depois")
    w("")
    w("1. `docs/arquitetura.md` — a arquitetura explicada didaticamente")
    w("2. `docs/HANDOFF.md` — estado atual, decisões vigentes, pendências")
    w("3. `docs/adr/` — o porquê de cada decisão estrutural")
    w("4. `docs/comandos-dev.md` — os comandos do dia a dia comentados")
    w("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if docs/dev-index.md is stale")
    args = parser.parse_args(argv)
    content = render()
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        if current != content:
            print("STALE: docs/dev-index.md — regenerate with tools/gen_dev_index.py")
            return 1
        print("dev-index fresh")
        return 0
    TARGET.write_text(content, encoding="utf-8")
    print(f"dev-index written: {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

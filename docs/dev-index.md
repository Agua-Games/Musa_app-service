<!--- GERADO por tools/gen_dev_index.py — não editar à mão; edite o gerador. -->

# Dev index — mapa vivo do repositório MUSA

> Gerado em máquina local · plataforma **v0.6.0** · contrato do card **v1.2.0**. Ponto de entrada para agentes de IA e devs novos:
> leia este arquivo PRIMEIRO, depois `docs/arquitetura.md`. Referência de
> API: `docs/api-reference.md` (gerada). Comandos: `docs/comandos-dev.md`.

## O sistema em um parágrafo

MUSA é um app-service para museus: o cliente tem um **repositório de conteúdo**
(cards + assets + config — zero código nosso) e a plataforma distribui um
**artefato** (imagem de contêiner `ghcr.io/agua-games/musa-app:<versão>`) que
constrói e serve o site do museu. Tier e módulos vêm de **entitlements
assinados Ed25519**; o gate garante que draft e conteúdo acima do tier nunca
chegam ao payload publicado.

## Componentes

| Onde | O que é | Arquivos-chave |
|---|---|---|
| `builder/musa_build/` | o motor: build do site estático + API dinâmica (serve) + gate do contrato | cli.py, build.py, serve.py, gate.py, contract.py, entitlements.py, pages.py, api.py |
| `builder/musa_build/schemas/` | schema do card embutido no artefato (uma fonte de verdade, com teste de drift) | card.schema.json |
| `source/` | o frontend (landing + acervo + viewers 3D + admin) — é também o template do site do cliente | index.html, assets/js/main.js, assets/css/style.css |
| `pipeline/` | catalogação assistida por IA (M2): OCR → estruturação LLM → cards; venv próprio em pipeline/.venv | README, build_vector_index.py |
| `mcp_server/` | servidor MCP stdio (8 ferramentas) — opera o acervo a partir de qualquer cliente MCP/agente | server.py, tools.py |
| `beta/` | cliente virtual: personas, gerador de uso indevido, bateria de edge cases, harness de serve | run_beta.py, personas.py, misuse.py, edge.py, harness.py, invariants.py |
| `tools/` | ferramentas de plataforma (uma por arquivo, com docstring de uso) | — |
| `schemas/` | contrato do card versionado (fonte canônica; o builder embute uma cópia) | card/v1/card.schema.json, COMPATIBILITY.md |
| `docs/` | documentação viva (HANDOFF, planos de milestone, ADRs, SLOs, runbook, modelos legais) | HANDOFF.md, adr/ |
| `.github/workflows/` | CI da plataforma, release do artefato (tag v* → imagem no ghcr.io), Pages | ci.yml, release.yml, pages.yml |

## Suítes de teste (rodar antes de push)

| Suíte | Comando | Cobre |
|---|---|---|
| `builder/tests/` | `cd builder && python -m unittest discover -s tests` | contrato, gate, build, serve, páginas, backup, alertas… |
| `mcp_server/tests/` | `cd mcp_server && python -m unittest discover -s tests` | as 8 ferramentas + smoke do protocolo stdio |
| `beta/tests/` | `python -m unittest discover -s beta/tests -t .` | harness, personas, misuse, edge battery |

## Ferramentas de plataforma (tools/)

| Arquivo | O que faz |
|---|---|
| `tools/check_alerts.py` | M4.4 — SLO alert check over a serve JSONL log (thin CLI wrapper) |
| `tools/check_frontend.py` | Fail the build on frontend mistakes that only surface in a browser |
| `tools/demo_narrative.py` | M4.7 — the 5-minute investor narrative, EXECUTED end to end (not narrated) |
| `tools/dr_drill.py` | M4.4 — DR drill: disaster -> restore -> verified service, timed |
| `tools/fetch_assets.py` | Download public-domain museum imagery from Wikimedia Commons into |
| `tools/fetch_models.py` | Fetch the 3D models used by the frontend demo into source/assets/models/ |
| `tools/fetch_vendor.py` | Vendor three.js into source/assets/vendor/ (browser ES modules, no bundler) |
| `tools/gen_dev_index.py` | Generate docs/dev-index.md — the always-fresh entry point for AI agents |
| `tools/logread.py` | Read a log **selectively**, and keep the folder it lands in from growing forever |
| `tools/make_demos.py` | M4.7 — generate the three fictional demo museums (one per tier), local-first |
| `tools/sign_entitlements.py` | MUSA platform tool — sign a client repository's entitlements (ADR 0010) |
| `tools/validate_catalog.py` | Validate the frontend catalog against the collection contract |

## Números atuais (auto-gerados)

- Cards de schema: 1 · ADRs: 17 · docs: 32 na raiz de docs/
- Testes: 18 arquivos no builder, 1 no MCP server, 4 no beta

## Para onde ir depois

1. `docs/arquitetura.md` — a arquitetura explicada didaticamente
2. `docs/HANDOFF.md` — estado atual, decisões vigentes, pendências
3. `docs/adr/` — o porquê de cada decisão estrutural
4. `docs/comandos-dev.md` — os comandos do dia a dia comentados

# MUSA — app-service para museus

O MUSA transforma o acervo de um museu em uma presença digital completa:
site público com catálogo pesquisável, modelos 3D interativos, gêmeo digital
das salas, cinema de arte online, loja e um assistente de IA que conhece
cada peça — publicado a partir de um repositório de conteúdo que **pertence
ao museu**, sem que ele precise escrever uma linha de código.

- **Para quem visita**: [`docs/visao-geral.md`](docs/visao-geral.md) — o que é, o que faz, diferenciais (linguagem leiga).
- **Para quem desenvolve**: [`docs/arquitetura.md`](docs/arquitetura.md) — a arquitetura explicada do zero.
- **Para agentes de IA / onboarding rápido**: [`docs/dev-index.md`](docs/dev-index.md) — mapa vivo do repo (gerado por `tools/gen_dev_index.py`).
- **Estado atual e pendências**: [`docs/HANDOFF.md`](docs/HANDOFF.md) · **API**: [`docs/api-reference.md`](docs/api-reference.md) · **Comandos**: [`docs/comandos-dev.md`](docs/comandos-dev.md).

## O modelo em 30 segundos

```
repo do museu (dele)              plataforma (nossa)                 público
┌────────────────────┐   build    ┌──────────────────────────┐
│ museum.config.json │ ─────────► │ artefato musa-app:X.Y.Z  │ ──► site estático (Pages)
│ content/  (cards)  │            │  · valida o contrato     │
│ assets/            │   serve    │  · aplica o gate de tier │ ──► API dinâmica (admin)
│ entitlements ✍︎     │ ◄───────── │  · assina/atualiza plano │
└────────────────────┘            └──────────────────────────┘
```

O museu nunca toca no motor; a plataforma nunca toma o acervo. Upgrades de
plano são uma **re-assinatura criptográfica** de um arquivo — sem migração,
sem reinstalação.

## Convenções da casa

Docs em português, código e commits em inglês (`tipo(escopo): …`).
Testes antes de push: `cd builder && python -m unittest discover -s tests`
(e `mcp_server/`, `beta/tests/` — ver `docs/comandos-dev.md`).
Repositório **privado**: preços, estratégia e segredos de negócio vivem aqui.

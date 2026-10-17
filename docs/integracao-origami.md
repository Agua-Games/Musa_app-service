# Integração Origami — MUSA plugado no orquestrador do estúdio

> **Público:** devs da Agua-Games que operam o MUSA através do Origami
> (orquestrador de apps via MCP e CLI) ou de um agente de IA acoplado a ele.
> 2026-10-17 · plataforma v0.6.0. Pré-requisito: ler `docs/dev-index.md`
> (mapa vivo) e, na primeira vez, `docs/arquitetura.md`.

## 1. As três superfícies que o Origami consome

| Superfície | Como o Origami usa | Para quê |
|---|---|---|
| **MCP stdio** (`mcp_server/`) | registra como MCP server | operar o acervo de um museu em linguagem natural (8 ferramentas) |
| **CLI** (`musa-build …`, `tools/*.py`) | executa como processo | builds, validação, release, demos, logs |
| **Docs gerados** (`docs/dev-index.md`, `docs/api-reference.md`) | aponta na config do agente | o agente programa com awareness sem re-digerir o repo |

## 2. MCP — registro no Origami

O servidor é stdio puro, zero dependências além do builder
(protocolo 2025-06-18, implementado em `mcp_server/server.py`). Um registro
**por repositório de museu** (`--repo` define qual acervo):

```json
{
  "mcpServers": {
    "musa-demo-museum": {
      "command": "python",
      "args": ["-m", "mcp_server", "--repo", "H:\\Musa_app-service\\DemoMuseum"],
      "cwd": "H:\\Musa_app-service\\alpha"
    }
  }
}
```

Ferramentas expostas (detalhe e regras: `docs/mcp-server.md`):

| Ferramenta | Faz | Escreve? |
|---|---|---|
| `list_collections` / `get_item` / `search` / `search_semantic` | leitura do acervo; resultados citam `asset_id` e caminho do card | — |
| `validate_card` / `propose_card_correction` | valida contra o contrato; corrige o mecânico, sinaliza o que é conteúdo | — |
| `set_status` | publica/despublica uma peça | ✅ card.json |
| `build_report` | roda o build real e devolve o "por que não apareceu?" | — (temp dir) |
| `upload_asset` | stub honesto (ADR 0009) — indica o workaround | — |

Invariáveis que o agente herda do servidor: **drafts são visíveis via MCP,
nunca no site**; toda afirmação sobre o acervo cita fonte; a única escrita é
atômica por arquivo.

## 3. CLI — os verbos que o Origami orquestra

```
musa-build validate  --repo <cliente> --frontend <alpha>/source   # gate sem emitir
musa-build build     --repo <cliente> --frontend <alpha>/source --out <dir>
musa-build serve     --repo <cliente> --port 8000                 # API dinâmica (admin)
musa-build audit     --repo <cliente>                             # prova do gate (M4.3)
musa-build backup / restore --repo <cliente>                      # overlay (M4.4)
musa-build api-reference [--check]                                # doc da API
```

Ferramentas de plataforma (uma por arquivo; lista viva em `docs/dev-index.md`):

```
python tools/sign_entitlements.py sign --repo <cliente> --key <chave-plataforma>  # upgrade/tier
python tools/make_demos.py --key <chave>        # regenera os 3 demos
python tools/demo_narrative.py --repo <demo> --key <chave>   # narrativa de investidor
python tools/logread.py read --file <log>       # SEMPRE para ler logs
python tools/gen_dev_index.py [--check]         # regenera o mapa vivo
```

## 4. Awareness do agente (o "índice sempre fresco")

Cadeia de leitura recomendada na sessão do agente do Origami:

1. `docs/dev-index.md` — **sempre primeiro** (gerado; regenere com
   `tools/gen_dev_index.py` após mudança estrutural).
2. `docs/api-reference.md` — endpoints, gerado do código (`--check` no CI).
3. `AGENTS.md` do repo — regras duras (Cloudflare/custos, logread, Windows).

Num `.env`/`.ini` do Origami, basta apontar o caminho fixo — o arquivo é
regenerado no lugar:

```ini
[musa]
repo = H:\Musa_app-service\alpha
agent_index = docs/dev-index.md
api_reference = docs/api-reference.md
```

## 5. Fronteiras de segurança (o que o Origami NÃO faz sozinho)

- **`MUSA_ADMIN_TOKEN`**: sem ele, o `serve` é read-only (writes = 503). O
  token vive em env/secret do ambiente, nunca no repo nem em args de linha
  de comando logados.
- **Chave Ed25519 da plataforma** (`H:\Musa_app-service\secrets\`):
  `sign_entitlements.py` é operação da plataforma — o Origami pode disparar,
  mas a chave nunca sai da pasta de secrets nem aparece em logs.
- **Cloudflare/R2**: a conta vigente é pessoal e temporária do dono
  (AGENTS.md). Nenhum fluxo do Origami move megabytes no R2 sem confirmar
  conta/bucket/cartão antes.
- **Escrita em produção**: push no repo de um cliente dispara o CI dele
  (build + deploy). O Origami só pusha com confirmação explícita do operador.

## 6. Receitas prontas (fluxos típicos)

**"Cliente novo quer ver o acervo no ar localmente"**
`musa-build validate` → `musa-build serve` (com token) → landing na porta
escolhida. Narrativa completa: `tools/demo_narrative.py` (5 beats, ~5 s).

**"Subiu versão da plataforma"**
Origami edita o pin `"musa"` no `museum.config.json` do cliente → push →
CI do cliente constrói com a imagem nova → Pages.

**"Algo não apareceu no site"**
MCP `build_report` (a linha do motivo) → se o card está inválido,
`validate_card` + `propose_card_correction`.

**"Ler o log de um incidente"**
`tools/logread.py read --file <log>` — nunca `cat` (AGENTS.md).

## 7. Checklist de plugue

- [ ] Registro MCP no Origami por museu (§2) — DemoMuseum primeiro.
- [ ] `agent_index` apontado para `docs/dev-index.md` (§4).
- [ ] `MUSA_ADMIN_TOKEN` no secret store do Origami (não no config em texto).
- [ ] Fluxo de release (tag `v*` → ghcr → re-pin) mapeado como pipeline
      restrito a operadores humanos.

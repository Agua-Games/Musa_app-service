# Servidor MCP do MUSA (M1.6)

> Operar o acervo de um museu a partir de qualquer cliente MCP (Kimi Work,
> Claude, Cursor…): ergonomia de desenvolvimento, base do assistente de IA e
> canal de operação — três papéis, uma superfície.

## Rodando

```bash
python -m mcp_server --repo ../DemoMuseum
```

Config de cliente MCP (ex.: `mcpServers` do Claude Desktop / Kimi Work):

```json
{
  "mcpServers": {
    "musa-demo": {
      "command": "python",
      "args": ["-m", "mcp_server", "--repo", "H:\\Musa_app-service\\DemoMuseum"],
      "cwd": "H:\\Musa_app-service\\alpha"
    }
  }
}
```

Zero dependências além do builder: o loop JSON-RPC stdio é implementado em
`mcp_server/server.py` (initialize, ping, tools/list, tools/call — protocolo
2025-06-18). O protocolo vai no stdout; mensagens humanas no stderr.

## Ferramentas

| Ferramenta | O que faz | Escreve? |
|---|---|---|
| `list_collections` | Coleções com tier, contagem de itens e status no portão | — |
| `get_item` | Ficha completa de uma peça + decisão do portão | — |
| `search` | Busca por termos; **todo resultado cita `asset_id` e o caminho da ficha** | — |
| `validate_ficha` | Valida uma ficha contra o contrato v1 congelado | — |
| `propose_ficha_correction` | Corrige o que é mecânico (identidade da pasta, status default) e **sinaliza** o que é conteúdo (nunca inventa) | — |
| `set_status` | Publica/despublica uma peça (`website_status` na ficha) | ✅ ficha.json |
| `build_report` | Roda o build real e devolve o relatório — "por que esta peça não apareceu?" em uma linha | — (temp dir) |
| `upload_asset` | **Stub honesto**: bloqueado na M1.3 (ADR 0009); indica o workaround (arquivo ao lado da ficha) | — |

## Regras que o servidor obedece

1. **A fonte de verdade é o repo do cliente** (o seed — ADR 0003). O MCP lê
   `content/` diretamente, com a *mesma* maquinaria do builder (`read_content`,
   validador do contrato, portão, índice de busca) — a ferramenta nunca
   diverge do build.
2. **Rascunhos são visíveis aqui, nunca no site.** O MCP é ferramenta de
   operação: `search` encontra `draft`s (e diz o status); o site publicado
   continua sem servi-los nem como arquivo.
3. **Toda afirmação sobre o acervo cita fontes** (`asset_id:…`, caminho da
   ficha) — a regra de `implementacao-usd.md` §7.
4. **`set_status` é a única escrita** e é atômica por arquivo; o efeito no site
   vem no build seguinte (o portão fica no build — HANDOFF §0.2).

## Verificação

`mcp_server/tests/` — 13 testes: toolbox sobre o fixture (critério de saída:
busca rastreável a `asset_id`), smoke do protocolo stdio (initialize →
tools/list → tools/call), e prova de que `set_status` escreve e reverte.

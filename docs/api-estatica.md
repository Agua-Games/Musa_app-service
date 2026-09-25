# API estática do acervo — shapes de resposta (M1.1)

> Implementa a spec §6.1 como arquivos JSON emitidos pelo builder (ADR 0008).
> O frontend consome estes arquivos em modo `live` + `static`; o backend
> dinâmico (M1.4) servirá **os mesmos shapes** — nenhum código de view muda.

## Layout emitido

```
api/schema.json                    o contrato da ficha, verbatim
api/collections.json               lista de coleções incluídas
api/collections/<id>/items.json    itens incluídos da coleção
api/items/<id>.json                ficha completa de uma peça
api/search.json                    índice de termos pré-computado + registros resumidos
```

Todos os arquivos já passaram pelo **portão do build**: um item `draft` ou acima
do tier contratado **não existe como arquivo** — o 404 do host é a resposta
"not found" da API.

## Envelope

Todo recurso (exceto `schema.json`, que é o contrato verbatim) usa o envelope:

```json
{
  "data": { },
  "meta": {
    "contract": "schemas/ficha/v1/ficha.schema.json",
    "generated": "2026-09-25",
    "museum": "demo-museum",
    "count": 5
  }
}
```

- `data` — o payload do recurso (objeto ou lista).
- `meta.contract` — o caminho do contrato que os registros em `data` obedecem.
- `meta.generated` — data do build que emitiu a API.
- `meta.museum` — `museum.id` do cliente.
- `meta.count` — presente em listas: número de registros em `data`.

## Erros

| Situação | Resposta |
|---|---|
| Recurso inexistente (`api/items/<id>.json` sem arquivo) | **404** do host estático — o cliente mapeia para "not found" (`undefined`) |
| Coleção não publicada neste build (`api/collections/<id>/items.json` sem arquivo) | 404 → o cliente serve **lista vazia** (rascunhos/tiers acima não vazam nem a existência) |
| Escrita (`POST /items`, etc.) | A API estática é **read-only**: o frontend rejeita localmente com mensagem clara ("needs the MUSA backend") |

## Paginação

O modo estático serve listas completas com `meta.count` (o acervo de um museu
cabe em memória no navegador). O backend dinâmico adicionará `?cursor=…` /
`?limit=…` **sem mudar o envelope** — clientes antigos simplesmente recebem a
primeira página completa.

## Busca estática (`api/search.json`)

Sem backend, a busca é um índice invertido pré-computado no build:

```json
{
  "data": {
    "terms": { "vermeer": ["moça-com-brinco"], "óleo": ["moça-com-brinco", "…"] },
    "items": { "moça-com-brinco": { "asset_id": "…", "titulo": "…", "autor": "…", "image": "…" } }
  }
}
```

- `terms` — token → `asset_id`s. Tokenização: minúsculas, split em não-`[^\w]+`,
  tokens com ≥ 2 caracteres. Campos indexados: `titulo`, `autor`, `descricao`,
  `material`, `colecao`, `subcolecao`, `tags`.
- `items` — registros **resumidos** (suficientes para renderizar o cartão de
  resultado sem segundo request). A ficha completa vem de `api/items/<id>.json`.
- Consulta = interseção dos buckets dos tokens; sem interseção, o frontend cai
  para substring sobre os resumos (mesma semântica do mock). Busca **semântica
  (RAG)** é M2 — o shape já comporta trocar o miolo.

## Configuração do frontend

O builder emite `data/runtime.js` em cada site de cliente:

```js
window.MUSA_RUNTIME = { mode: "live", baseUrl: "api", static: true };
```

`main.js` aplica no boot (`MusaAPI.configure`). O demo da plataforma
(`source/`) carrega um stub com `mode: "mock"` — catálogo em memória.

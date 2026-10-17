# API reference — MUSA collection API (`musa_build serve`)

> **Gerado automaticamente — não editar à mão.** Regenere com `cd builder && python -m musa_build api-reference` (a suíte de testes falha se este doc ficar velho em relação ao código). Conceitos, justificativas e o porquê das decisões: `docs/api-dinamica.md` e `docs/api-estatica.md`.

Plataforma **v0.4.0** · contrato do card **v1.2.0** (`schemas/card/v1/card.schema.json`).

## Convenções

- **Envelope**: toda rota de dados responde `{ data, meta }` — `meta` carrega `contract`, `generated`, `museum` e `count` (listas). Exceções: `/health`, `/schema`, `/auth/login`, `/assistant/ask` e os binários de `/assets/…`. Detalhes em `docs/api-estatica.md`.
- **Auth**: escritas e visão de rascunhos exigem `Authorization: Bearer <MUSA_ADMIN_TOKEN>`. Sem token configurado a instância é read-only e escritas respondem 503.
- **Portão (gate)**: registros `draft` ou acima do tier do museu são 404 para o público — não vazam nem a existência.
- **Erros**: corpo `{ "detail": "…" }` (FastAPI). Tabela completa por endpoint abaixo; resumo:

  | Código | Significado |
  |---|---|
  | 401 | token ausente/inválido em rota protegida |
  | 403 | verificação anti-robô (Turnstile) falhou |
  | 404 | recurso inexistente **ou** excluído pelo portão |
  | 409 | conflito: duplicado ou `_rev` estagnado |
  | 422 | validação (slug, coleção, contrato) — a mensagem aponta o campo |
  | 429 | rate limit ou cota diária do assistente (header `Retry-After`) |
  | 503 | instância sem `MUSA_ADMIN_TOKEN` (writes disabled) ou assistente indisponível |

## Ops

### `GET /health`

Liveness. Informa versão da plataforma, versão do contrato e se a instância aceita escritas (`writes`).

- **Auth**: público
- **Resposta**: `{"status": "ok", "museum": "…", "version": "…", "contract": "…", "writes": "enabled|disabled"}`

### `GET /schema`

O contrato do card (`card.schema.json`), verbatim — o mesmo arquivo que o build usa no portão de validação.

- **Auth**: público
- **Resposta**: o JSON Schema do contrato, sem envelope

## Leitura (pública)

### `GET /collections`

Coleções **incluídas** (publicadas e dentro do tier). Uma coleção excluída pelo portão não aparece nem como existente.

- **Auth**: público
- **Resposta**: envelope com lista de coleções

### `GET /collections/{collection_id}/items`

Itens incluídos da coleção. `?include_drafts=1` exige token e devolve também os rascunhos (visão do admin).

- **Auth**: público; `include_drafts=1` exige token
- **Query** `include_drafts` (bool, padrão `False`)
- **Resposta**: envelope com lista de cards
- **Erros**:
  - `401` — `include_drafts=1` sem token válido
  - `404` — coleção inexistente **ou excluída pelo portão** (draft/tier) — não vaza nem a existência
  - `503` — instância sem `MUSA_ADMIN_TOKEN` (writes disabled) ao pedir drafts

### `GET /items/{asset_id}`

Card completa de uma peça. Com token, o admin enxerga os próprios rascunhos; o portão de tier nunca relaxa.

- **Auth**: público; drafts só com token
- **Resposta**: envelope com o card
- **Erros**:
  - `404` — item inexistente, draft sem token, ou acima do tier

### `GET /search`

Busca por interseção de tokens sobre o índice dos itens públicos. `q` vazio devolve lista vazia.

- **Auth**: público
- **Query** `q` (str, padrão `''`)
- **Resposta**: envelope com os cards que contêm **todos** os tokens

### `GET /cinema/programme`

Programação de cinema do museu (seção da loja/vitrine; módulo `cinema`).

- **Auth**: público
- **Resposta**: envelope com lista de sessões/filmes

### `GET /store/products`

Produtos da loja (módulo `store`).

- **Auth**: público
- **Resposta**: envelope com lista de produtos

### `GET /plans`

Planos de assinatura exibidos pelo site do museu.

- **Auth**: público
- **Resposta**: envelope com lista de planos

## Assistente (M4.2)

### `POST /assistant/ask`

Pergunta em linguagem natural sobre o acervo (módulo `assistant`). A resposta é **grounded**: o provedor de LLM só recebe as fichas públicas recuperadas do índice de busca e um system prompt que descreve os campos do card e proíbe inventar além delas. Camadas anti-abuso, da mais barata à mais cara: Turnstile (só com `MUSA_TURNSTILE_SECRET` configurado), rate limit por IP (`MUSA_ASSISTANT_RPM`, padrão 10/min), respostas prontas para saudações e visão geral do acervo (custo zero), recusa de off-topic **sem chamar o provedor**, cota diária de tokens por museu (`MUSA_ASSISTANT_DAILY_TOKENS`, padrão 200 mil) e circuit breaker de provedor (5 falhas seguidas abrem por 5 min). Corpo: `{question, context?}`; o token do Turnstile vai em `turnstile_token` ou `context.turnstile_token`. Cada ask é logado (`assistant_ask`) com estimativa de custo e hash do IP (nunca o IP cru). Sem provedor configurado (`DEEPSEEK_API_KEY` ou `MUSA_LLM_FAKE=1`) → 503.

- **Auth**: público (rate-limited)
- **Resposta**: `{"answer": "…", "suggestedArtifacts": [{id, title}]}` — **sem envelope**
- **Erros**:
  - `403` — verificação Turnstile falhou (quando configurada)
  - `404` — museu sem o módulo `assistant` — não vaza nem a existência
  - `422` — `question` vazia ou acima de 2000 caracteres
  - `429` — rate limit por IP **ou** cota diária de tokens esgotada (header `Retry-After`)
  - `503` — assistente não configurado, ou provedor fora do ar (circuit breaker aberto)

## Escrita (admin)

### `POST /auth/login`

Login do admin do tenant: o **token do tenant vai no campo `password`**. Devolve o token e um perfil mínimo. Contas com papéis/SSO chegam com o backend de escala (ADR 0008).

- **Auth**: corpo: `{email, password}`
- **Resposta**: `{"token": "…", "user": {email, name, role, org, note}}`
- **Erros**:
  - `401` — credenciais inválidas
  - `503` — instância sem `MUSA_ADMIN_TOKEN` configurado

### `POST /collections`

Cria coleção. Corpo: `{id, title, description?, tier?, cover?, website_status?}` — `id` é slug minúsculo; tier padrão `bronze`. Coleção criada como draft responde `visible: false` (existe, mas o público não vê).

- **Auth**: token (admin)
- **Resposta**: 201 + envelope com a coleção criada
- **Erros**:
  - `401` — sem token válido
  - `409` — coleção já existe — nunca sobrescreve
  - `422` — `id` fora do padrão de slug (`a-z`, `0-9`, `-`)
  - `503` — instância sem `MUSA_ADMIN_TOKEN`

### `POST /items`

**Patch** de card existente (`{asset_id, ...campos}`) ou **criação** (card completo; nasce `draft` — publicar é um patch explícito). Guardas (achados do M3.2): corpo de criação (com `colecao`) para `asset_id` existente → 409; `_rev` implementa concorrência otimista (patch com `_rev` velho → 409); patch sem `_rev` é last-write-wins, por desenho. Um escritor por vez (lock de escrita).

- **Auth**: token (admin)
- **Resposta**: 200 + envelope com o card resultante
- **Erros**:
  - `401` — sem token válido
  - `409` — create duplicado **ou** `_rev` estagnado — re-ler e reaplicar
  - `422` — slug inválido, coleção desconhecida ou card fora do contrato (mensagem aponta o campo)
  - `503` — instância sem `MUSA_ADMIN_TOKEN`

## Assets (binários)

### `GET /assets/content/{collection}/{rest:path}`

Binário de um asset (imagem, `.glb`, …). Somente assets de registros **incluídos**: coleção excluída, dotfile, nome reservado (`card.json`, …) ou fuga de diretório → 404. `_skin/<arquivo>` serve os arquivos de skin da raiz do repo.

- **Auth**: público (gated)
- **Resposta**: o arquivo binário (`FileResponse`)
- **Erros**:
  - `404` — asset inexistente ou bloqueado pelo portão

## Contrato do card (campos)

Fonte: `builder/musa_build/schemas/card.schema.json` (v1.2.0). Obrigatórios: `asset_id`, `titulo`, `colecao`.

| Campo | Tipo | Descrição (verbatim do contrato) |
|---|---|---|
| `asset_id` **(obrigatório)** | string · pattern `^[A-Za-z0-9._-]+$` | Unique asset identifier. Also the folder name of the item. |
| `titulo` **(obrigatório)** | string | Title of the piece. |
| `autor` | string | Author or creator. |
| `data` | string | Date as free display text — real museum dating is fuzzy ('17th century', '1801-1900', 'late 16th-early 17th century'), so this field stays unconstrained. For sorting/filtering, use the optional structured companion data_iso. |
| `data_iso` | string · pattern `^-?\d{1,4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$` | Normalized date for machines: YYYY, YYYY-MM or YYYY-MM-DD; BCE dates are negative numbers (e.g. -500). Optional; when present it must be exact. Added in 1.1.0 (compatible: optional field). |
| `material` | string | Predominant material. |
| `dimensoes` | string | Physical dimensions as free text (e.g. 30cm x 20cm). |
| `descricao` | string | Long description. |
| `licenca` | string | Rights statement of the media/record (e.g. 'CC0 1.0', 'Domínio público', 'CC BY-SA 4.0'). Optional; rendered in the item view so every public asset shows its license (LGPD/licensing milestone M4.6). Added in 1.2.0 (compatible: optional field). |
| `fonte` | string | Source of the media/record — the institution or URL the asset came from (e.g. 'The Metropolitan Museum of Art', a Wikimedia Commons URL). Optional; rendered with licenca. Added in 1.2.0 (compatible: optional field). |
| `colecao` **(obrigatório)** | string | Collection this item belongs to; must match a top-level folder under acervo/. |
| `tags` | lista de string | Keywords. |
| `model_primary` | string | Asset the frontend loads today (e.g. model.glb). Required when model_status is available. |
| `model_source` | string | Source asset for editing and archiving (e.g. asset.usda). Optional; absent in the GLB-only MVP. |
| `model_formats` | lista de enum: `glb`, `gltf`, `usd`, `usda`, `usdc`, `usdz` | Formats actually available for this item. |
| `model_viewer` | enum: `three_js`, `usd_wasm`, `kit_stream` | Viewer that must be used to render model_primary. |
| `model_status` | enum: `available`, `processing`, `unavailable` | State of the 3D pipeline for this item. |
| `digital_twin_sala` | string | Reference to the digital twin of the room where the piece is displayed. |
| `embedding` | lista de number | Semantic embedding of the record, used for retrieval (RAG). |

Regra condicional: se `model_status` é `available`, `model_primary` passa a ser obrigatório (`allOf` do schema). Campos extras são permitidos (`additionalProperties: true`).

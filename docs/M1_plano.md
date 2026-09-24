# M1 — MVP funcional: plano de ataque

> **Objetivo do milestone** (HANDOFF §9): um museu real consegue operar o sistema sozinho
> para o caso básico. Este plano sequencia os 8 entregáveis do M1 em fases com
> verificação própria — nenhuma fase termina sem uma prova que pode falhar.
>
> Ponto de partida: M0 concluído (2026-09-23). O que já existe e o M1 **não** refaz:
> contrato v1 congelado, builder com portão e gating, artefato em contêiner no ghcr.io,
> CI da plataforma e do cliente, template de cliente, DemoMuseum publicado.

---

## Restrições que o plano obedece (não reabrir sem ADR)

1. **Contrato primeiro** — a API serve o contrato v1; mudança incompatível é v2, nunca edição.
2. **O portão fica no build** — a API nunca serve `draft` nem tier acima do contratado,
   e o build continua sendo a última linha de defesa.
3. **Binário grande não entra no git** — object storage é pré-requisito, não opcional.
4. **Repo do cliente = seed versionado; edições do dia a dia = banco** (ADR 0003). O admin
   **não** escreve em git.
5. **Não fazer no M1:** autenticação de visitante, multi-tenant, OCR (é o M2), USD no browser.

---

## Fase M1.0 — Decisões de arquitetura (3 ADRs, ~1 sessão)

Três decisões bloqueiam tudo; tomá-las por escrito antes de codar.

| Decisão | Opção recomendada | Alternativa | ADR |
|---|---|---|---|
| **Backend do acervo** | API própria mínima (FastAPI ou Express) servindo o contrato, com caminho documentado para Payload quando o admin exigir CMS completo | Payload desde já (mais pesado: Node + Postgres + S3 desde o dia 1) | 0008 |
| **Object storage** | Azure Blob Storage (a hospedagem-alvo é App Service; um fornecedor só) | Cloudflare R2 (sem egress) ou Backblaze B2 (mais barato) | 0009 |
| **Entitlements** | Arquivo assinado (Ed25519): plataforma assina offline, builder verifica com chave pública embarcada; endpoint online vem com o backend | Servidor de entitlements desde já (exige auth e deploy antes da hora) | 0010 |

**Verificação:** os 3 ADRs commitados; cada um lista a opção descartada e o motivo.

---

## Fase M1.1 — API de acervo em modo estático (a espinha dorsal)

A spec §6.1 define `/collections`, `/items/{id}`, `/search`, `/schema`. O MVP serve isso
**estaticamente**: o builder passa a emitir, além do `catalog.js`, a API em JSON
(`api/collections.json`, `api/items/<id>.json`, `api/search.json`, `api/schema.json`) —
a mesma forma que o backend dinâmico servirá depois, então **nenhum código de view muda**
quando o backend chegar (é o que `api.js` já promete com os modos `mock`/`live`).

1. Definir os shapes de resposta (envelope, erros, paginação) — documento na spec.
2. Builder emite a API estática (gating já aplicado — a API estática herda o portão).
3. `api.js` ganha modo `live` apontando para os JSONs estáticos; o DemoMuseum liga o modo.
4. `search` estático: índice pré-computado por termo (sem backend, semântica vem no M2).

**Verificação:** o site do DemoMuseum funciona com `MUSA_MODE=live` servindo só JSONs
estáticos; um item `draft` não existe em `api/items/` (nem como arquivo).

## Fase M1.2 — Entitlements reais (assinatura offline)

1. Ferramenta da plataforma `tools/sign_entitlements.py` (chave privada Ed25519 fora do
   repo, em secret) — assina `museum.config.json → entitlements`.
2. Chave pública embarcada no artefato; o builder **falha o build** se a assinatura não
   confere ou o tier difere do emitido. O *warning* de "assinatura ausente" vira erro —
   exceto em modo desenvolvimento (`musa: "0.0.0-unreleased"`).
3. Token de deploy por cliente (escopo: este museu, estas ações) — prepara o M3/M4.

**Verificação:** adulterar o tier no `museum.config.json` do DemoMuseum **falha o build**
(falsificável, como o gating do M0).

## Fase M1.3 — Object storage

1. Bucket/container por cliente (`musa-assets-<museum-id>`), ciclo de vida e CORS.
2. `python -m musa_build upload --repo .` — sobe os assets locais de `content/` e
   **reescreve a ficha** para a URL pública (a ficha versionada fica com a URL, não o
   binário — o repo do cliente emagrece com o tempo, não engorda).
3. O builder resolve `storage.assetsBaseUrl` e valida que os assets respondem (HEAD 200)
   antes de publicar.

**Verificação:** subir um GLB novo no DemoMuseum sem nenhum binário no commit; o site
publicado carrega o modelo do bucket.

## Fase M1.4 — Admin mínimo (aqui entra o backend)

O admin mockado atual vira real **contra a API** — criar coleção, subir item,
publicar/despublicar, promover hero. É aqui que a decisão da M1.0 pesa: se a API própria
mínima mostrar limite (revisão, histórico, usuários), o Payload entra **nesta fase**, não
antes. O repo do cliente continua sendo o *seed* (conteúdo inicial versionado); as edições
do dia a dia vivem no banco (ADR 0003).

**Verificação:** um curador não-técnico cria uma coleção e publica um item **sem ajuda**,
cronometrado — o critério é **< 15 min**.

## Fase M1.5 — Logger estruturado + depurador de conteúdo

1. Log JSON com correlation ids `tenant → build → asset` no builder e na API.
2. O build report (M0) ganha a visão de API: "esta peça não apareceu" responde em uma
   linha **também quando o dado veio do banco**, não só do repo.

**Verificação:** reproduzir um build inteiro a partir dos logs; o report explica 100%
das inclusões/exclusões (já é critério do M0 para o repo — estender ao banco).

## Fase M1.6 — Servidor MCP do MUSA

Ferramentas mínimas sobre a API: `list_collections` · `get_item` · `search` ·
`validate_ficha` · `propose_ficha_correction` · `upload_asset` · `set_status` ·
`build_report`. Toda resposta que afirma algo sobre o acervo **cita as fontes**
(regra já escrita em `implementacao-usd.md` §7). Três papéis ao mesmo tempo: ergonomia de
desenvolvimento, base do assistente de IA, canal de operação.

**Verificação:** `search` responde com fontes rastreáveis a `asset_id` (critério de saída).

## Fase M1.7 — DemoMuseum com conteúdo real

Migrar o acervo demo da plataforma (`source/data/catalog.json`, 14 itens) para
`content/` no formato do contrato — o DemoMuseum deixa de ser exemplo e vira **réplica
operacional** de um museu, com assets no bucket (M1.3), não no git.

**Verificação:** os 4 critérios de saída do M1 (abaixo) medidos no DemoMuseum.

---

## Critérios de saída do M1 (do HANDOFF, com a fase que os prova)

| Critério | Fase |
|---|---|
| Curador não-técnico cria coleção e publica item sem ajuda, em **< 15 min** | M1.4 |
| Build report explica 100% das inclusões/exclusões | M1.5 |
| `search` responde com fontes rastreáveis a `asset_id` | M1.6 |
| Upgrade de versão no cliente = 1 linha + push, verde no CI | ✅ **já provado no M0** — manter verde |

## Ordem e dependências

```
M1.0 (decisões) ──► M1.1 (API estática) ──► M1.4 (admin/backend) ──► M1.7 (conteúdo real)
       │                   │                       │
       ├──► M1.2 (entitlements, independente)      ├──► M1.5 (logs, transversal)
       └──► M1.3 (storage) ────────────────────────┴──► M1.6 (MCP)
```

M1.2 e M1.3 podem correr em paralelo com M1.1 se houver uma segunda pessoa. A trilha de
risco a medir cedo (§10 do HANDOFF): **custo de operação do backend por cliente** — ele
define se o preço do tier se sustenta.

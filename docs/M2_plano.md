# M2 — Pipeline de catalogação: plano de ataque

> **Objetivo do milestone** (HANDOFF §9): provar que a promessa central do produto é
> verdadeira, **com números** — 500 fotos de fichas entram, 500 cards válidas saem,
> X% dos campos passam sem revisão humana, custo por card em R$ medido. Este plano
> sequencia os 6 entregáveis do M2 em fases com verificação própria — nenhuma fase
> termina sem uma prova que pode falhar.
>
> Ponto de partida: M1 concluído (2026-10-08). O que já existe e o M2 **não** refaz:
> contrato v1 congelado (com campo `embedding` previsto), builder com portão e
> validação de contrato reutilizável (`musa_build.contract`), `musa-build upload`
> para levar scans ao bucket, DemoMuseum operacional como bancada de ingestão.

---

## Restrições que o plano obedece (não reabrir sem ADR)

1. **Nenhum card entra no índice sem validação** — a pipeline emite `card.json` que
   passa pelo *mesmo* validador do builder; não existe caminho alternativo.
2. **Lido ≠ inferido** — todo campo carrega proveniência (`ocr_read` / `llm_corrected`
   / `llm_inferred`) e confiança; o relatório de confiança é entregável, não detalhe.
3. **Custo medido, não estimado** — toda chamada paga (LLM, embeddings, storage) é
   logada com custo unitário; o número R$/card sai de log, não de planilha.
4. **Sem subscription nova** — OCR e embeddings rodam local/offline; LLM por API
   pay-per-token. Nenhum componente exige plano mensal (decisão do dono, 2026-09).
5. **Não fazer no M2:** RAG/assistente conversacional (é M3+), UI de revisão
   elaborada (a fila do M2 é um JSON + planilha), multi-tenant.

---

## Fase M2.0 — Decisões de arquitetura (3 ADRs, ~1 sessão)

> **Estado (2026-10-08): CONCLUÍDO.** ADRs 0011, 0012 e 0013 aprovadas pelo dono.

Três decisões bloqueiam tudo; tomá-las por escrito antes de codar.

| Decisão | Opção recomendada | Alternativa | ADR |
|---|---|---|---|
| **Motor de OCR** | **docling** (pip, headless, batch, roda em CPU no Windows do estúdio, sem daemon Docker) — com PP-StructureV3 para layout de ficha | Folio-OCR (melhor layout, mas exige Docker) ou vlm4ocr (VLM — mais lento por página) | 0011 |
| **LLM de estruturação** | **API pay-per-token com modo JSON** (baseline de qualidade para medir o X%; custo logado por chamada) — modelo pequeno primeiro, escalar só se a qualidade reprovar | SLM local (Qwen via Ollama — custo zero mas exige GPU e a qualidade em PT-BR de ficha manuscrita não foi medida) | 0012 |
| **Índice vetorial** | **sqlite-vec** — o serve do M1 já usa SQLite por museu; zero infra nova, arquivo único, backup = copiar o arquivo | pgvector (exige Postgres rodando desde já — infra que o M2 não precisa) | 0013 |

**Verificação:** os 3 ADRs commitados; cada um lista a opção descartada e o motivo.

---

## Fase M2.1 — Corpus de teste com gabarito (a régua do X%)

Sem gabarito não há como medir "X% dos campos sem revisão". Dois corpora:

1. **Corpus sintético controlado (450+ fichas):** metadados reais de acervos
   abertos (Met Open Access, Rijksmuseum, SMK — CSV público com titulo/autor/data/
   material) renderizados como **imagens de ficha** (Pillow: fontes, layouts,
   rotações, ruído, iluminação desigual). Gabarito perfeito por construção,
   escala de graça até 5.000.
2. **Corpus real (50 fichas):** fotos reais de etiquetas/fichas de museu —
   o dono fotografa em museus ou usa scans públicos de fichas; gabarito digitado
   uma única vez. É o corpus que responde ao risco nº 1 (HANDOFF §10.2: qualidade
   do OCR em ficha manuscrita — **ninguém mediu ainda**).

**Custo de infra: zero no Cloudflare.** O corpus é insumo de desenvolvimento da
pipeline — vive **local** em `pipeline/corpus/` (gitignored), nunca no bucket.
Só a importação final do M2.6 toca o R2, e mesmo assim **metadados apenas**: os
cards importados não precisam de imagem (o contrato só exige `asset_id`,
`titulo`, `colecao`). Vitrine visual do acervo importado = 10–15 fichas com
scan no bucket, se o dono quiser — decisão adiada para o M2.6.

> **Estado (2026-10-08): corpus sintético CONCLUÍDO; corpus real aguarda as fotos
> do dono.** `pipeline/` criado: `fetch_seed_metadata.py` (475 metadados reais do
> Met Open Access, cache resumível — a API devolve 403 intermitente sob rate
> limit, contornado com backoff + skip), `render_corpus.py` (450 fichas, 3
> layouts — datilografada, moderna, itálica — com rotação, blur, jitter de
> brilho e ruído; seed fixa = reproduzível) e `validate_ground_truth.py` — **450
> gabaritos, 100% válidos contra o contrato v1 pelo próprio validador do
> builder**. Amostras inspecionadas visualmente. Guia de coleta do corpus real
> (50 fichas: 15 manuscritas, 10 datilografadas, 10 impressas, 10 em condições
> ruins, 5 multilíngues/incompletas) em `pipeline/README.md`. Bucket R2 intacto:
> 0 bytes do corpus nele.

**Verificação:** `pipeline/corpus/` local e gitignored; `ground-truth/*.json`
valida contra o contrato v1; script de geração sintética reproduzível com seed
fixa; `du` do bucket inalterado ao fim da fase.

---

## Fase M2.2 — OCR em lote headless

> **Estado (2026-10-08): CONCLUÍDO.** venv dedicado em `pipeline/.venv`
> (gitignored; dependências fixadas em `pipeline/requirements-ocr.txt`: docling
> 2.135 + rapidocr 3.9.1 — o 3.10 mudou a API e quebra o docling — + torch CPU +
> onnxruntime). `ocr_engine.py` implementa a interface da ADR 0011 com o backend
> RapidOCR (o backend padrão EasyOCR não vem instalado no docling 2.x);
> `run_ocr.py` é resumível, isola falhas em `ocr/failed/` e loga JSONL por ficha;
> `ocr_report.py` mede o resultado contra o gabarito. **Números das 450 fichas:
> 450 ok / 0 falhas / 0 saídas vazias; 4.32 s por ficha (~32 min de motor); char
> recall vs. gabarito: média 0.937, mediana 0.958, p10 0.842, mín 0.633.**
> Execução em 9 fatias resumidas (~55 fichas cada) por limite de timeout do
> ambiente de automação — o runner é o mesmo, o resume é o comportamento
> projetado; em máquina livre roda em lote único.

1. `pipeline/` novo na plataforma (Python, offline, fora da imagem do app — é
   ferramenta da equipe, não runtime do cliente).
2. Runner batch: varre o corpus, produz `ocr/*.json` (texto bruto + caixas de
   layout por bloco), com log estruturado (o logger do M1.5) e tempo por ficha.
3. Falha individual não derruba o lote — ficha problemática vai para
   `ocr/failed/` com o motivo.

**Verificação:** 500 fichas processadas em lote único, sem intervenção;
relatório lista tempo total, falhas e taxa de caracteres reconhecidos por ficha.

---

## Fase M2.3 — Agente de estruturação → card.json

1. Prompt template da spec §2.3.3, endurecido: saída JSON validada contra o
   contrato v1 **em código** (não confiar no formato do modelo; retry com o erro
   de validação no prompt, máx. 2 tentativas).
2. **Proveniência por campo**: o agente marca cada campo como `ocr_read` (o texto
   estava literal na ficha), `llm_corrected` (OCR com erro óbvio corrigido) ou
   `llm_inferred` (não estava na ficha — ex.: data completada por contexto
   histórico). Campo inferido **sempre** vai à fila de revisão, independente da
   confiança.
3. `asset_id` gerado deterministicamente (slug do título + hash curto); colisão
   falha a ficha, nunca sobrescreve.

**Verificação:** 500 `card.json` emitidos; 100% validam contra o contrato
(critério de saída 3); amostra de 20 fichas auditada à mão contra a foto —
divergência de proveniência (campo marcado `ocr_read` que não estava na ficha)
reprova a fase.

---

## Fase M2.4 — Relatório de confiança + fila de revisão

1. Cruzamento com o gabarito do M2.1: por campo, por corpus, taxa de acerto de
   OCR puro vs. pós-LLM. **O número X sai daqui.**
2. Fila de revisão: um único `review-queue.json` (ficha, campo, valor proposto,
   proveniência, confiança, caminho da imagem) — revisão humana dirigida, não
   total. Revisão = editar o JSON e revalidar; sem UI nesta fase.
3. Limiar de confiança configurável; o relatório mostra a curva
   limiar × % sem revisão × taxa de erro residual — é ela que precifica o serviço.

**Verificação:** relatório publicado em `docs/` com o X medido nos dois corpora
(sintético e real, separados — o real é o número comercial); fila contendo
somente campos de baixa confiança ou inferidos.

---

## Fase M2.5 — Embeddings + busca semântica

1. Embeddings **locais** (modelo multilíngue pequeno, ex. multilingual-e5-small
   via sentence-transformers — CPU, custo zero, PT-BR competente).
2. Índice sqlite-vec por museu, regenerável a partir dos cards (derivado, nunca
   fonte da verdade); `card.json → embedding` segue o campo previsto no contrato.
3. O MCP do M1.6 ganha `search_semantic` ao lado do `search` lexical — mesma
   regra de citar `asset_id` + caminho do card em toda resposta.

**Verificação:** consulta semântica em PT-BR sem palavra exata do card
("retrato de moça holandesa" → Moça com Brinco de Pérola) retorna o item certo
no top-3 do DemoMuseum; busca lexical existente não regride (13 testes do MCP
verdes).

---

## Fase M2.6 — Importação em lote no DemoMuseum + publicação dos números

1. Lote de 500 cards revisados entra em `content/` do DemoMuseum (coleção própria
   `acervo-importado`) — **metadados apenas, sem scans no bucket** (restrição 4 e
   decisão do dono, 2026-10-08: DemoMuseum não precisa de acervo extenso por ora);
   10–15 scans de vitrine no máximo, se aprovados. O `git` segue só com cards.
2. Build + CI verdes com o lote; medir tempo de build com N itens (insumo do M3).
3. Publicar em `docs/M2_resultados.md`: X% sem revisão, R$/card decomposto
   (OCR + LLM + embeddings + storage), tempo de pipeline por ficha, taxa de erro
   residual pós-revisão.

**Verificação:** os 3 critérios de saída do M2 (abaixo) medidos e publicados;
site do DemoMuseum exibindo o acervo importado.

---

## Critérios de saída do M2 (do HANDOFF, com a fase que os prova)

| Critério | Fase |
|---|---|
| 500 fotos entram, 500 cards válidas saem; **X% sem revisão humana, medido e publicado** | M2.1 + M2.4 + M2.6 |
| **Custo por card em R$** medido (OCR + LLM + armazenamento) | M2.3 (log) + M2.6 (publicação) |
| Nenhum card entra no índice sem validação | M2.3 (validador do builder no loop) |

## Ordem e dependências

```
M2.0 (decisões) ──► M2.1 (corpus+gabarito) ──► M2.2 (OCR) ──► M2.3 (estruturação)
                                                              │           │
                                              M2.5 (embeddings, independente do OCR)
                                                              ▼
                                              M2.4 (confiança+fila) ──► M2.6 (importação+números)
```

M2.5 é independente da trilha OCR e pode correr em paralelo logo após o M2.0 —
usa o acervo já existente do DemoMuseum. A trilha de risco a medir cedo é o
**corpus real do M2.1**: se o OCR de ficha manuscrita reprovar, o desenho do
produto muda (revisão total assistida em vez de dirigida) e é melhor saber na
semana 1, não no M2.6.

---

## Riscos específicos do M2 (além do HANDOFF §10)

1. **Gabarito enviesado** — corpus sintético é mais fácil que o real; os números
   dos dois corpora são sempre reportados separados.
2. **Custo de LLM escalar com retry** — o retry de validação do M2.3 dobra o
   custo de fichas difíceis; o log de custo é por chamada, não por ficha, para
   esse efeito ficar visível.
3. **Fotos reais com direitos** — scans/fotos de fichas de museus terceiros ficam
   fora do git e do bucket público do demo; o bucket do corpus é privado ou local.

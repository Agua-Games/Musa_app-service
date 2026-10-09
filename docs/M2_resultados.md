# M2 — Resultados medidos da pipeline de catalogação

> **Corpus sintético (450 fichas, gabarito perfeito) — medido em 2026-10-08.**
> O número comercial definitivo vem do corpus real (fichas manuscritas/fotos de
> verdade), cuja coleta está **adiada** (cliente real ou geração por IA — ver
> `pipeline/README.md`). Os números abaixo são a régua otimista: ficha
> datilografada/impressa, boa iluminação simulada. Reportamos os dois corpora
> sempre separados (risco 1 do plano).

## Os números

| Métrica | Valor |
|---|---|
| Fichas processadas ponta-a-ponta | **450/450** (OCR 0 falhas · estruturação 0 falhas, 0 retries) |
| Campos medidos contra o gabarito | 2.219 |
| OCR puro legível | 86,3% dos campos |
| Pós-LLM correto (todos os campos) | 92,2% |
| **X% sem revisão (regra por confiança, limiar 0.7)** | **93,5%** — com **6,9% de erro residual** |
| **X% sem revisão (regra estrita de proveniência)** | **76,6%** — com **1,4% de erro residual** |
| Custo LLM total / por ficha | US$ 0,0588 / **≈ R$ 0,0007 por ficha** (câmbio aprox. 5,4) |
| Custo OCR + embeddings | R$ 0 (local, CPU) |
| Tempo de pipeline por ficha | ~4,3 s (OCR) + ~1,8 s (LLM) ≈ **6,1 s** |

## O achado de produto: a confiança auto-reportada não vale; a proveniência vale

A curva limiar × auto-aprovação × erro residual ficou **plana de 0.0 a 0.8** —
o modelo raramente reporta confiança baixa, então filtrar por confiança quase
não remove erro. O sinal real está na **proveniência do campo**:

| Proveniência | n | % correto |
|---|---|---|
| `ocr_read` | 1.699 | **98,6%** |
| `llm_corrected` | 377 | 68,2% |
| `llm_inferred` | 138 | 82,6% (vai à fila sempre, por regra) |

Recomendação de operação (regra B): auto-aprovar só `ocr_read`; `llm_corrected`
e `llm_inferred` vão à fila de revisão dirigida. Custo: 23,4% dos campos
revisados por humano; ganho: erro residual cai de 6,9% para **1,4%**.

## Por campo (pós-LLM)

| Campo | n | % correto | % auto-aprovado (regra confiança 0.7) |
|---|---|---|---|
| título | 450 | 99,1 | 100,0 |
| autor | 91 | 100,0 | 100,0 |
| data | 416 | 91,6 | 84,4 |
| material | 448 | 98,2 | 99,3 |
| dimensões | 364 | 98,4 | 99,5 |
| descrição | 450 | 73,3 | 83,3 |

Comparadores por campo (documentados em `pipeline/confidence_report.py`):
título/autor/material = recall estrito de tokens; data = anos e era preservados
(o LLM normaliza formato por instrução); dimensões = todos os números do
gabarito; descrição = recall de palavras de conteúdo ≥ 0,5 (gabarito é
telegráfico, card é sentença). `tags` não entram na régua: são enriquecimento
inferido por design, não transcrição.

## Fila de revisão

`pipeline/corpus/review-queue.json`: **145 campos** (6,5% do total) — ficha,
campo, valor proposto, gabarito, proveniência, confiança e caminho da imagem.
Revisão = editar o JSON e revalidar; UI de revisão não faz parte do M2.

## Limitações honestas

1. **Corpus sintético**: ficha renderizada é mais limpa que foto real; manuscrito
   não foi medido (risco nº 1 do HANDOFF continua aberto até o corpus real).
2. **Gabarito Met → layout de ficha nosso**: mede a pipeline, não um museu
   específico; cada cliente terá seu layout de ficha.
3. Tarifas DeepSeek com referência 2026-05; o custo final R$/card sai do log por
   chamada na importação do M2.6.

---

## Importação no DemoMuseum (M2.6, 2026-10-09)

- **450 cards importados** em `content/acervo-importado/` — só metadados (565 KB
  no git, **0 bytes no bucket**): 308 publicados, 142 em `draft` aguardando a
  revisão dirigida (regra: campo na fila que não seja `tags` mantém o rascunho).
- **Build com 463 itens: 7,3 s** local; CI do DemoMuseum (build na imagem pinada
  + deploy Pages): **36 s**, verde no primeiro push.
- Site publicado exibe o acervo importado; rascunhos visíveis só no admin.
- Modo batch do agente (medido, 20 fichas/1 request): ~150 tokens de entrada por
  ficha (vs. ~476 solo), −29% de custo, 14 s de parede — default recomendado
  para acervos reais.

**M2 encerrado com ressalva explícita:** os critérios foram medidos no corpus
sintético; o número comercial definitivo depende do corpus real (coleta adiada
— ver `pipeline/README.md`).

# ADR 0012 — LLM de estruturação: API pay-per-token com modo JSON, custo logado por chamada

- **Status:** aceita
- **Data:** 2026-10-08
- **Relacionada:** ADR 0011 (OCR), spec §2.3.3, `docs/M2_plano.md` fases M2.3/M2.4

## Contexto

Depois do OCR, um modelo de linguagem corrige erros de reconhecimento e
estrutura o texto no esquema da ficha universal (spec §2.3.3) — o `card.json`
do contrato v1. Duas exigências do milestone pesam mais que a escolha do modelo:

1. **O número X% é o produto.** "X% dos campos passam sem revisão humana" define
   o preço do serviço (HANDOFF §9, M2). Para medir X com credibilidade, o
   baseline de qualidade precisa ser o melhor modelo que couber no custo — não o
   mais barato que rodar.
2. **O custo por card em R$ é critério de saída.** Ele só é honesto se cada
   chamada paga for logada com tokens e preço unitário — inclusive os retries,
   que dobram o custo das fichas difíceis (risco 2 do plano M2).
3. **Regra do dono (2026-09): sem subscription nova.** Isso elimina planos
   mensais de LLM, não APIs pay-per-token — estas cobram só o uso medido.
4. **O contrato v1 é o portão**: a saída do LLM é validada em código contra o
   schema; formato inválido nunca entra no índice (restrição 1 do plano M2).

## Decisão proposta

1. **API pay-per-token com modo JSON/structured output** como baseline do M2.3,
   começando pelo **modelo pequeno do provedor** (barato) — escalar para o modelo
   maior só se a taxa de acerto por campo reprovar na medição do M2.4.
2. **Provedor atrás de interface** (`pipeline/structure/llm.py`):
   `structure(ocr_json, schema) -> (card_json, provenance, usage)` — trocar de
   provedor ou modelo é configuração, não código.
3. **Validação em código, retry finito**: saída que não valida contra o contrato
   volta ao modelo com o erro de validação no prompt, **máx. 2 tentativas**;
   depois disso a ficha vai para `review-queue.json` como falha de estruturação.
4. **Proveniência por campo é obrigatória na saída**: `ocr_read` /
   `llm_corrected` / `llm_inferred`. Campo inferido vai à fila de revisão
   sempre, independente da confiança (restrição 2 do plano M2).
5. **Log de custo por chamada** (tokens in/out, modelo, preço unitário do dia,
   correlation id da ficha) no logger estruturado do M1.5 — o R$/card do M2.6 é
   uma agregação desse log.
6. **Credencial da API fora do repo**, em `H:\Musa_app-service\secrets\` — mesmo
   padrão das credenciais R2 do M1.3.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **SLM local via Ollama (Qwen etc.)** | Custo marginal zero, mas qualidade em PT-BR sobre OCR ruidoso de ficha nunca foi medida e o hardware do estúdio não foi dimensionado para lote; vira o experimento de redução de custo do M2.6, com o baseline medido |
| **Extração determinística (regex + layout)** | Deve existir como **grupo de controle** na medição (é o "sem LLM" que prova o valor do LLM), mas sozinha não corrige erro de OCR nem infere — reprova o critério X% em fichas reais |
| **Subscription de LLM (plano mensal)** | Rejeitada pela regra do dono; e pay-per-token é mais barato no volume do M2 (centenas de fichas, não milhões) |
| **Gerar embeddings na mesma chamada** (spec §2.3.3 sugere) | Mistura dois custos e dois pontos de falha; embeddings são locais e grátis na M2.5 (ADR 0013) |

## Consequências

- O X% medido tem credibilidade comercial: baseline com modelo bom, custo real
  logado, grupo de controle determinístico para comparação.
- Trocar de provedor (ou migrar para SLM local quando a qualidade estiver
  medida) é mudança de configuração.
- O custo das fichas difíceis fica visível no log (retries), não escondido na
  média.
- Risco aceito: dependência de internet durante o M2.3; mitigado pelo lote ser
  reexecutável (fichas já estruturadas são puladas).
- Quando houver cliente real, o texto OCR de fichas dele sairia para a API —
  decisão de privacidade/LGPD adiada para o M4, dona de uma ADR própria.

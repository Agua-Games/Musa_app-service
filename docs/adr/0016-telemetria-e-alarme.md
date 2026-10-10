# ADR 0016 — Telemetria e alarme do cliente virtual: JSONL por cenário, artifact no run, falha abre issue

- **Status:** aceita (2026-10-10, dono)
- **Data:** 2026-10-09
- **Relacionada:** ADR 0014 (driver das personas), ADR 0015 (execução
  nightly), `docs/M3_plano.md` fases M3.3/M3.4, HANDOFF §M3 itens 3–4

## Contexto

Um nightly que ninguém lê é pior que nenhum — cria falsa sensação de
cobertura. O M3 precisa que cada execução produza evidência estruturada e
que **falha vire issue automaticamente** (critérios de saída 1 e 3). O que
pesa:

1. **Evidência estruturada, não log de texto**: para medir "14 dias sem
   regressão" e alimentar os SLOs do M3.6, cada ação de persona e cada
   cenário de uso indevido precisa ser um registro consultável (cenário,
   ação, resultado, latência, invariantes verificados, veredito).
2. **Alarme com dedup**: uma regressão que dura 5 noites não pode abrir 5
   issues — e uma regressão corrigida deve fechar a issue com referência ao
   run que a curou. Caso contrário o alarme vira ruído e passa a ser
   ignorado (a falha clássica de monitoramento).
3. **Retenção e custo**: artifacts do GitHub Actions retêm 90 dias por
   padrão — suficiente para o beta (14 dias de critério + margem). Serviço
   de observabilidade é subscription — vetado pela regra de custo do dono.
4. **O relatório é um entregável do milestone**: a lista priorizada de bugs
   conhecidos (critério de saída 3) nasce do acúmulo desses relatórios —
   então o formato precisa agregar por cenário/fingerprint, não ser apenas
   um dump cronológico.
5. **Padrão já existente**: o builder já emite log estruturado JSONL
   (`build-log.jsonl`, M1.5) com correlação — o M3 segue o mesmo padrão em
   vez de inventar outro.

## Decisão proposta

1. **JSONL por cenário** — cada execução grava um evento por ação:
   `{run_id, timestamp, cenario, persona, acao, alvo, resultado,
   latencia_ms, invariantes: [{nome, ok, detalhe}], veredito}`. Formato
   alinhado ao `build-log.jsonl` do M1.5.
2. **Relatório agregado por run** — resumo por cenário (passa/falha/
   regressão-nova/regressão-conhecida/curada), publicado como **artifact do
   workflow** (`beta-report-<run>.json` + `beta-report-<run>.md` legível).
3. **Falha abre issue via `gh`** no repo do DemoMuseum, com:
   - **fingerprint** estável do cenário (hash de `cenario + acao +
     invariante`) no título/label — dedup: falha já aberta recebe
     **comentário** com o novo run, não issue nova;
   - sucesso após falha **fecha a issue** referenciando o run da cura;
   - labels `beta-nightly` + `regressao` para filtrar o acumulado.
4. **Sem dados sensíveis no JSONL** — tokens, chaves e conteúdo de campos
   ficam fora; o log carrega IDs, vereditos e latências (o repo é público).
5. **Agregação para os critérios**: script `beta/report.py` lê os artifacts
   recentes e produz o estado dos 14 dias (dias verdes consecutivos,
   regressões abertas, bugs conhecidos priorizados) — é dele que sai a
   publicação do critério de saída 3.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **Só o log do Actions** | Texto não estruturado, apodrece em 90 dias, impossível agregar "14 dias sem regressão" sem parsing frágil |
| **Serviço de observabilidade** (Sentry, Datadog, Grafana Cloud) | Subscription ou cota apertada; o volume do beta (dezenas de eventos/noite) não justifica — vetado pela regra de custo |
| **Issues sem dedup** | Ruído: regressão de 5 noites = 5 issues; o alarme passa a ser ignorado e o critério deixa de significar algo |
| **E-mail/webhook de alerta** | Caixa de entrada não é backlog — a issue é o artefato priorizável que o critério de saída 3 exige |
| **Commitar relatórios no repo** | Polui o histórico do cliente com ruído operacional diário; artifact + issue já dão rastreabilidade |

## Consequências

- "14 dias sem regressão" deixa de ser impressão e vira consulta sobre
  dados — o mesmo rigor dos números do M2.
- Regressões viram backlog priorizável automaticamente; a lista de bugs
  conhecidos do critério 3 é efeito colateral do processo, não trabalho
  extra no fim do milestone.
- O padrão JSONL + artifact + issue é reutilizável pelo M4 (monitoramento
  de produção) — o M3 já deixa o esqueleto.
- Risco aceito: retenção de 90 dias dos artifacts — se o beta se estender
  além disso, os relatórios-chave (ex.: o que fecha os 14 dias) são
  promovidos a `docs/` antes de expirar.

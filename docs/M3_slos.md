# M3.6 — SLOs com números reais

> Revisão da tabela §8.1 da spec (2026-10-12). Cada métrica tem: alvo proposto,
> número **MEDIDO** (com data e cenário) ou marcação honesta (**ESTIMATIVA** /
> **NÃO MEDIDO**), veredito e ação. É o material que vai na proposta comercial
> do M4 — nenhum alvo sem número correspondente.
>
> Fontes: `docs/M3_carga.md` (carga, 2026-10-12), `docs/M2_resultados.md`
> (pipeline de catalogação), runs de CI do DemoMuseum (publicação fim-a-fim).

## Tabela final

| Métrica | Alvo proposto (spec §8.1) | Medido / estimado | Medido em | Veredito |
|---|---|---|---|---|
| Tempo de build do acervo | < 10 min p/ 1.000 peças | **2,2 s** para 1.000 cards; 17,0 s para 10.000 (linear, ~1,7 ms/item) — MEDIDO | 2026-10-12, `beta/load.py`, corpus sintético Met | **Cumprido com folga ~270×** — alvo mantido (cobre máquinas piores e assets reais) |
| Fichas rejeitadas na validação | 0 em produção | **0 rejeições** em todos os builds do DemoMuseum desde o M1.7; rejeição correta de cards inválidos coberta pelos testes de uso indevido — MEDIDO | CI deploy.yml (runs verdes 2026-10-08→12) + M3.2 | **Cumprido** |
| Tempo de carga do GLB (p75) | < 3 s por peça em 4G | NÃO MEDIDO — exige rede/dispositivo real | — | **Pendente do beta real (M3.7)**; alvo mantido como proposto |
| Cache hit do CDN | > 90% | NÃO SE APLICA ainda — assets saem do bucket público `r2.dev`, sem CDN contratual | — | **Pendente da arquitetura de entrega (M4)** |
| Latência p95 de `/items/{id}` | < 300 ms | **16 ms** em 10.000 itens (limite do tick do agendador — ler como "≤16 ms") — MEDIDO | 2026-10-12, escala 10k | **Cumprido com folga ~19×** |
| Latência p95 de `/search` *(linha nova, M3.6)* | — | **32 ms** em 1.000 itens; **235 ms** em 10.000 (cresce linear) — MEDIDO | 2026-10-12, `beta/load.py` | **Alvo formal proposto: p95 < 500 ms @10k** — cumprido hoje; otimização (índice pré-computado) só se um acervo >10k aparecer |
| Publicação fim-a-fim (push → site no ar) *(linha nova, M3.6)* | — | **30–51 s**, mediana 36 s (463 itens, build+deploy no GitHub Actions) — MEDIDO | runs 37709664721…38190534255 (2026-10-08→12) | **Alvo formal proposto: < 2 min** — cumprido |
| Custo por consulta do assistente | dentro do previsto por tier | **≈ US$ 0,0004/consulta** (RAG top-k ≈ 10 cards × ~180 tokens + prompt ≈ 2–3k tokens de entrada; tarifa Deepseek ref. 2026-05) — ESTIMATIVA. Estruturação de ficha: ~150 tokens/card em batch (−29% vs. solo) — MEDIDO | M2.5 (batch) + fórmula | **Dentro do previsto**; revisar tarifa antes de precificar |
| Custo de armazenamento | acompanhar GB/mês | JSON: 1.803 bytes/card MEDIDO → 10k cards ≈ US$ 0,0002/mês; com assets típicos (2.000 fotos × 500 KB) ≈ R$ 0,08/mês + ~R$ 1/mês de leituras — fórmula MEDIDA + ESTIMATIVA de assets | `docs/M3_carga.md` §3 | **Cumprido** — base de preço documentada; R2 é centavos, compute (M4) é o custo real |
| Qualidade da recuperação (RAG) | reavaliar a cada 6 meses | **76,6%** dos campos auto-aprovados pela regra estrita de proveniência, com **1,4%** de erro residual — MEDIDO | M2.4, corpus sintético com gabarito | **Cadência mantida**; próxima revisão com corpus real (pendente do dono) |
| Disponibilidade do site/API | *(sem alvo na spec)* | NÃO MEDIDO — depende de GitHub Pages + `r2.dev` (SLA do provedor, não nosso) | — | **Proposto: repassar 99,9% do provedor**; medir com cliente real (M3.7) |
| RPO / RTO | *(backup na spec §7)* | **RPO ≈ 0** para o acervo versionado (o repo git é a fonte da verdade); edições de admin não commitadas vivem no overlay `.musa/` — RPO delas = até o próximo commit. **RTO ≈ 1 min** (redeploy = build+deploy medido) — MEDIDO/ESTIMATIVA | arquitetura ADR 0003 + runs de CI | **Proposto: RPO 0 / RTO < 5 min**; backup do overlay entra no M4 |

## Decisões tomadas nesta revisão

1. **Nenhum alvo medido reprovou** — nenhuma correção de produto necessária.
2. **Duas linhas novas** entram na tabela (search e publicação fim-a-fim): a
   spec não tinha alvo para elas e a medição mostrou que merecem SLO formal.
3. **Três pendências honestas** ficam para depois, com dono e gatilho claros:
   GLB em 4G (M3.7, precisa de rede real), cache de CDN (M4, precisa da
   arquitetura de entrega), disponibilidade (M3.7, precisa de cliente real).
4. **Nada vira SLO contratual** sem o número medido na frente do cliente — a
   coluna "Medido em" é a evidência.

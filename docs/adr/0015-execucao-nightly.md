# ADR 0015 — Execução nightly do cliente virtual: GitHub Actions no repo do DemoMuseum

- **Status:** proposta
- **Data:** 2026-10-09
- **Relacionada:** ADR 0005 (publicação do frontend), ADR 0006 (formato do
  artefato), ADR 0014 (driver das personas), `docs/M3_plano.md` fase M3.4,
  HANDOFF §M3 item 4 (nightly no CI)

## Contexto

O M3 exige **14 dias de nightly sem regressão** como critério de saída. Onde
e como o nightly roda é decisão de arquitetura, não detalhe — define custo,
fidelidade e quem é o "ator" do teste. O que pesa:

1. **O cliente virtual deve rodar onde o cliente vive**: o repo do
   DemoMuseum. O workflow sobe a **imagem publicada no ghcr.io** (o artefato
   real de distribuição, ADR 0006), clona o próprio repo para um diretório
   descartável e opera contra ele. Assim o nightly testa inclusive o caminho
   real de distribuição — não o código da working tree da plataforma.
2. **Custo**: o DemoMuseum é repo **público** → minutos de GitHub Actions
   são gratuitos. O repo da plataforma é privado → consumiria a cota de
   minutos da org. Regra de custo do dono: nenhuma subscription nova, nenhum
   gasto recorrente evitável.
3. **Isolamento (restrição nº 2 do plano M3)**: as escritas das personas
   ficam no overlay `.musa/` do clone temporário do runner; nada é
   commitado, nada é deployado. O site público do demo e o repo permanecem
   exatamente como o M2 os deixou. O workflow não tem `contents: write` no
   repo.
4. **Custo Cloudflare ~zero (restrição nº 4)**: cenários de upload usam
   storage local/simulado — nenhum upload real ao R2 no CI. A conta
   Cloudflare em uso é pessoal e temporária (nota no topo do HANDOFF);
   nenhum teste automatizado pode gerar transferência ou armazenamento
   recorrente nela.
5. **Horário**: `schedule` com cron em minuto fora de cheia —
   `17 3 * * *` (03:17 UTC = 00:17 em Brasília) — evitando a congestão dos
   minutos 0/30. `workflow_dispatch` permite rodada manual a qualquer
   momento.

## Decisão proposta

1. **Workflow `beta-nightly.yml` no repo DemoMuseum**, gatilhos
   `schedule: "17 3 * * *"` + `workflow_dispatch`.
2. Passos: checkout do DemoMuseum em diretório descartável → pull da imagem
   `ghcr.io/agua-games/musa-app:<tag pinada>` → sobe `serve` com token de
   teste → roda personas (ADR 0014) + gerador de uso indevido + invariantes
   → publica JSONL e relatório como artifact (ADR 0016).
3. **Sem escrita no repo, sem deploy, sem R2 real** — permissões do workflow
   restritas (`contents: read`, `issues: write` para o alarme do ADR 0016).
4. **Tag da imagem pinada e visível** no workflow — o nightly testa uma
   versão conhecida; bump da tag é commit explícito (o que também registra
   "qual versão do produto estava sob beta quando").
5. **Gatilho de revisão registrado**: se o DemoMuseum virar privado, os
   minutos passam a contar — reabrir esta decisão (mover o workflow para a
   plataforma ou ligar billing) antes de deixar a cota estourar.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **Nightly na máquina do estúdio** (Task Scheduler / Automation local) | A máquina precisa estar ligada e saudável toda madrugada; falha de energia/rede vira falha de produto falsa; não é CI auditável (sem histórico público de runs) |
| **Schedule no repo da plataforma (privado)** | Consome a cota de minutos da org; e o ator certo do beta é o **cliente** — o workflow morar no repo do cliente reforça que quem opera é o museu, não o fornecedor |
| **Azure (App Service / Container Apps job)** | Custo recorrente desde já e acopla o beta ao deploy de produção antes de ele existir — o M4 é que dimensiona Azure, com os números do M3.5 |
| **Rodar contra o código-fonte da plataforma em vez da imagem** | Testaria a working tree, não o artefato distribuído — exatamente o vício que o M3 existe para eliminar |

## Consequências

- O relógio dos 14 dias roda em infraestrutura gratuita, auditável (histórico
  de runs público) e independente da máquina de ninguém.
- Cada nightly prova que a **imagem publicada** opera o repo do cliente —
  regressão de distribuição (imagem quebrada, tag errada) é pega na hora.
- O DemoMuseum acumula dois papéis: demo pública (M1/M2) e bancada do
  cliente virtual (M3) — com isolamento garantido por permissões do
  workflow, não por disciplina.
- Risco aceito: Actions de repo público é grátis hoje; mudança de política
  do GitHub ou de visibilidade do repo reabre a decisão (gatilho registrado
  no item 5).

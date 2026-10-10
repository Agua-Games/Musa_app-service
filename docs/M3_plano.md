# M3 — Beta / cliente virtual: plano de ataque

> **Objetivo do milestone** (HANDOFF §M3): encontrar o que ninguém pensou, **antes
> do cliente pagante**. O cliente virtual no DemoMuseum não é um teste de fumaça —
> é um ator: personas sintéticas operam o produto todos os dias, um gerador de uso
> indevido tenta quebrá-lo, e cada ação é seguida de asserções de invariante.
> Este plano sequencia os 7 entregáveis do M3 em fases com verificação própria —
> nenhuma fase termina sem uma prova que pode falhar.
>
> Ponto de partida: M2 concluído (2026-10-09). O que já existe e o M3 **não** refaz:
> `musa-build serve` (API dinâmica com overlay SQLite `.musa/`, gating idêntico ao
> build, token de tenant), `musa-build upload` (CLI para o R2), DemoMuseum
> operacional com CI verde (36 s com 463 itens), imagem no ghcr.io, MCP com busca
> lexical + semântica. Lacunas **já conhecidas** que as personas vão expor (não são
> surpresa — são backlog esperado): a API não tem endpoint de upload de asset, de
> despublicar/excluir, de desfazer, nem proteção explícita contra edição
> concorrente; o downgrade de tier é operação manual nossa.

---

## Restrições que o plano obedece (não reabrir sem ADR)

1. **O cliente virtual age pelo caminho do curador real** — HTTP contra a API do
   `musa-build serve` e os CLIs documentados. Nunca edita `.musa/` direto, nunca
   chama função interna do builder. Se uma rotina não é possível pela API, isso é
   um **achado** (bug ou lacuna), não um convite a atalho.
2. **As escritas das personas nunca poluem o repo público nem o site do Pages** —
   o nightly roda contra um clone descartável do DemoMuseum com overlay em
   diretório temporário; nada é commitado, nada é deployado. O repo e o site do
   demo continuam exatamente como o M2 os deixou.
3. **Toda ação é seguida de asserção de invariante** — nada `draft` no payload
   público, nada acima do tier, contrato válido, build verde. Uma ação sem
   asserção não conta como exercitada.
4. **Custo de infra ~zero no nightly** — GitHub Actions de repo público é
   gratuito; uploads de verdade ao R2 **não** acontecem no CI (cenários de upload
   usam storage local/simulado). A conta Cloudflare em uso é pessoal e temporária
   (nota no topo do HANDOFF) — nenhum teste automatizado pode gerar transferência
   ou armazenamento recorrente nela.
5. **Não fazer no M3:** backend multi-tenant definitivo, assistente conversacional
   público e sua política anti-abuso (M4), LGPD (M4), UI nova. Lacunas de API
   descobertas viram issues priorizadas — não são implementadas no susto, salvo
   quando bloqueiam uma rotina central (aí é bug, e entra).

---

## Fase M3.0 — Decisões de arquitetura (3 ADRs, ~1 sessão)

Três decisões bloqueiam tudo; tomá-las por escrito antes de codar.

| Decisão | Opção recomendada | Alternativa | ADR |
|---|---|---|---|
| **Driver das personas** | **Scripts Python dirigindo a API HTTP do `musa-build serve`** (o mesmo caminho do admin real) + CLI `musa-build upload` onde a API não cobre. Determinístico com seed, rápido, roda em CI | Playwright contra a UI do admin (cobre a UI, mas é frágil e lento — um smoke de UI separado pode vir depois); MCP (é ferramenta da equipe, não do curador); chamar funções internas (viola a restrição 1) | 0014 |
| **Execução nightly** | **GitHub Actions `schedule` no repo do DemoMuseum** (público → minutos grátis), cron em minuto fora de cheia (`17 3 * * *`), rodando a imagem do ghcr.io contra clone descartável — testa inclusive o caminho real de distribuição | Rodar nightly na máquina do estúdio (precisa estar ligada; não é CI do produto); schedule no repo da plataforma (privado consome cota de minutos; e o ator certo é o cliente, não o fornecedor) | 0015 |
| **Telemetria e alarme** | **JSONL por cenário + relatório agregado publicado como artifact do workflow; falha abre issue via `gh`** (com dedup por fingerprint do cenário) | Só o log do Actions (não estruturado, apodrece em 90 dias); serviço de observabilidade (subscription — vetado pela regra de custo) | 0016 |

**Verificação:** os 3 ADRs commitados; cada um lista a opção descartada e o motivo.

---

## Fase M3.1 — Personas sintéticas (`beta/personas/`)

> **Estado (2026-10-10): CONCLUÍDO.** Pacote `beta/` criado: `client.py`
> (sessão HTTP do curador), `personas.py` (`owner@demo` + `team@demo`,
> rotinas diária/semanal/pontual com seed determinística), `invariants.py`
> (a biblioteca do M3.3, nascida aqui conforme o plano) e `run_beta.py`
> (clone descartável → serve subprocess → rotinas → JSONL + relatório).
> **Rodada local verde contra o DemoMuseum** (`20261010T225529Z-seed42`):
> 17 eventos, 0 reprovações, os 4 achados-gap esperados classificados
> (upload de asset, PATCH de coleção, desfazer, canal de módulo); repo do
> DemoMuseum intacto (`git status` limpo — restrição 2 provada). 7 testes
> verdes, incluindo determinismo de seed (mesma seed ⇒ mesma sequência) e
> sanidade dos invariantes (cada um forçado a falhar uma vez). Armadilha
> documentada: polling de health logo após o bind do uvicorn precisa de
> timeout curto — no Windows a primeira conexão pode travar no kernel pelo
> timeout inteiro (ver `beta/client.py`).

1. **Duas personas** — `owner@demo` (pode tudo) e `team@demo` (papel restrito,
   quando papéis existirem; até lá opera com o mesmo token mas escopo menor de
   rotinas) — cada uma com rotinas:
   - *diária*: publicar 2 itens, corrigir um card, subir uma imagem;
   - *semanal*: criar coleção, reorganizar subcoleção, promover hero;
   - *pontual*: despublicar, desfazer, pedir um módulo novo.
2. **Determinismo com seed** — mesma seed, mesma sequência de ações; o cenário é
   reproduzível localmente com um comando.
3. **Rotinas expressas como chamadas HTTP/CLI** (restrição 1); cada rotina declara
   as asserções que a seguem (M3.3). Rotina impossível pela API atual vira achado
   registrado, não workaround interno.

**Verificação:** rodada local completa das duas personas contra o DemoMuseum
(clone descartável) termina verde; o log mostra cada ação com sua asserção; os
achados de lacuna de API já conhecidos aparecem classificados como tal.

---

## Fase M3.2 — Gerador de uso indevido (`beta/misuse/`)

Os 10 cenários do HANDOFF, cada um como script independente com **resultado
esperado explícito** (aceitar graciosamente ou rejeitar com erro útil — nunca
corromper estado nem perder dados):

| # | Cenário | Resultado esperado |
|---|---|---|
| 1 | Arquivo grande demais | Rejeição com limite declarado na mensagem |
| 2 | MIME errado | Rejeição na validação, nada gravado |
| 3 | Campo obrigatório ausente | Contrato rejeita; mensagem aponta o campo |
| 4 | `asset_id` duplicado | Conflito (409); nunca sobrescreve |
| 5 | Data inválida | Rejeição na validação do contrato |
| 6 | `.glb` corrompido | Rejeição; registro não fica pela metade |
| 7 | Upload interrompido | Estado consistente; retomada ou rollback |
| 8 | Edições concorrentes no mesmo card | Segundo escritor recebe conflito ou merge definido — nunca perda silenciosa |
| 9 | Token expirado/errado | 401/403; nenhuma escrita; público inalterado |
| 10 | Downgrade de tier no meio do caminho | Conteúdo acima do tier some do payload; volta intacto no upgrade |

**Verificação:** 10/10 cenários com veredito (passa / falha documentada); nenhum
causa perda de dados — essa é a linha vermelha absoluta do critério de saída.

---

## Fase M3.3 — Asserções de invariante (`beta/invariants.py`)

Biblioteca única, usada por personas e misuse após **cada** ação:

1. **Nada `draft` no payload público** — `/collections`, `/items` e o build
   estático não contêm registros draft (exceto com token e `include_drafts=1`).
2. **Nada acima do tier** — gating idêntico no serve e no build; assets de
   registros excluídos não são servidos (404).
3. **Contrato válido** — todo registro visível valida contra o contrato v1.
4. **Build verde** — `musa-build build` no estado atual termina sem erro.

**Verificação:** teste de sanidade que viola cada invariante de propósito (injeta
um draft, um item Gold em museu Bronze) e confirma que a asserção **pega** —
uma asserção que nunca falha no teste de sanidade não é asserção.

---

## Fase M3.4 — Telemetria + validação no CI

> **Emenda do dono (2026-10-10, ADR 0015):** sem cron permanente por ora — o
> workflow nasce **só com `workflow_dispatch`** (rodada de prova + re-rodada
> manual a cada mudança da plataforma). A linha `schedule:` (`17 3 * * *`)
> só entra quando houver cliente real, e o relógio dos 14 dias começa nesse
> momento. Direção fixada: build de cliente é **dirigido por evento**
> (adição/edição de peça marca o acervo "dirty" → rebuild), nunca por agenda.

1. Workflow `beta-validation.yml` no DemoMuseum (ADR 0015): sobe a imagem do
   ghcr, roda personas + misuse + invariantes, grava JSONL por cenário e
   relatório agregado como artifact.
2. **Falha abre issue** via `gh` com fingerprint do cenário (dedup: falha já
   aberta recebe comentário, não issue nova); sucesso após falha fecha com
   referência ao run.
3. **Critério dos 14 dias** começa a contar com o primeiro cliente real (ou
   beta fechado) — 14 dias corridos sem regressão aberta.

**Verificação:** um nightly forçado (`workflow_dispatch`) termina verde de ponta
a ponta; uma falha injetada de propósito abre issue e a recuperação a fecha.

---

## Fase M3.5 — Carga: N museus × M itens

1. **Escala de itens por museu**: builds sintéticos com 500 / 2.000 / 5.000 /
   10.000 cards (gerador reaproveita o `render_corpus.py` do M2 — metadados
   apenas, sem assets). Mede tempo de build, tamanho do payload, tempo de
   carregamento do serve e latência de `/search` e `/collections/{id}/items`.
   Baseline conhecido: 463 itens = 7,3 s de build local, 36 s de CI com deploy.
2. **Escala de museus**: N instâncias do serve na mesma máquina (isolamento por
   portas) — mede memória por instância e o ponto em que a máquina do estúdio
   deixa de ser suficiente (insumo direto para o dimensionamento do App Service
   no M4).
3. **Custo**: projeção R$/mês por museu por faixa de acervo (storage R2 +
   banda + compute), com os números medidos — alimenta a precificação junto com
   o X% do M2.

**Verificação:** tabela publicada em `docs/M3_carga.md` com as curvas medidas e
os pontos de quebra; nenhum número estimado sem marcação explícita.

---

## Fase M3.6 — SLOs com números reais

A tabela §8.1 da spec tem alvos **propostos**. Substituir por medições:

1. Para cada SLO proposto (disponibilidade, latência de leitura, tempo de build,
   tempo de publicação fim-a-fim, RPO/RTO), medir no nightly e na carga do M3.5.
2. Onde a medição reprovar o alvo proposto, decidir: corrige o produto ou corrige
   o alvo — por escrito (ADRs novas se mudar arquitetura).
3. Publicar a tabela final em `docs/` — é o material que vai na proposta
   comercial do M4.

**Verificação:** tabela §8.1 reescrita com coluna "medido em" (data + cenário);
nenhum alvo sem número correspondente.

---

## Fase M3.7 — Beta fechado com museu real

> **Bloqueado pelo dono** — depende da rede de contatos dele (amigo, parceiro,
> pequeno acervo). As fases M3.0–M3.6 preparam tudo para que o beta seja só
> onboarding.

1. Onboarding real pelo fluxo documentado (ADR 0003 + M1.7) — nada de acesso
   especial "de desenvolvedor".
2. **2 semanas de operação sem intervenção da equipe** — o critério é o museu
   operar sozinho; qualquer socorro nosso registra o motivo e vira bug ou
   melhoria de onboarding.
3. Coleta estruturada: o que o curador tentou e não achou, onde errou, o que
   pediu — alimenta a lista de bugs conhecidos priorizada (critério de saída).

**Verificação:** ata das 2 semanas (operação autônoma + incidentes); lista de
bugs conhecidos publicada e priorizada.

---

## Critérios de saída do M3 (do HANDOFF, com a fase que os prova)

| Critério | Fase |
|---|---|
| 14 dias de validação **sem regressão** (relógio começa com o 1º cliente real — emenda ADR 0015) | M3.4 |
| 100% dos cenários de uso indevido cobertos, **nenhum causa perda de dados** | M3.2 + M3.3 |
| Lista de bugs conhecidos priorizada e publicada | M3.1–M3.4 (achados) + M3.7 (consolidação) |
| Um museu real operou por 2 semanas sem intervenção da equipe | M3.7 (bloqueado pelo dono) |

## Ordem e dependências

```
M3.0 (decisões) ──► M3.1 (personas) ──► M3.2 (uso indevido) ──► M3.4 (nightly+telemetria)
                        │                     │
                        └──────► M3.3 (invariantes) ◄──────────┘
                                                              │
                                    M3.5 (carga) ◄────────────┘
                                        │
                                    M3.6 (SLOs reais)
                                        │
                                    M3.7 (beta real — bloqueado pelo dono)
```

M3.3 é biblioteca transversal: nasce junto com o M3.1 e é adotada pelo M3.2.
M3.5 só precisa do nightly de pé (usa a mesma infraestrutura de CI). M3.7 pode
começar a ser articulado pelo dono a qualquer momento — quanto antes houver um
museu candidato, mais cedo o relógio das 2 semanas pode correr.

---

## Riscos específicos do M3 (além do HANDOFF §10)

1. **Personas otimistas demais** — personas escritas por quem construiu o
   produto tendem a usar o produto "certo". Mitigação: o gerador de uso indevido
   (M3.2) é deliberadamente hostil, e o beta real (M3.7) é a correção final —
   personas sintéticas não substituem o curador de verdade.
2. **Falso verde no nightly** — asserção frouxa ou ambiente de CI diferente do
   real. Mitigação: o teste de sanidade do M3.3 força cada invariante a falhar
   uma vez; o nightly usa a imagem publicada do ghcr, não o código da working
   tree.
3. **Custo oculto de CI** — se o repo do DemoMuseum virar privado, os minutos de
   Actions passam a contar. Mitigação: o nightly é barato (uma imagem, um clone,
   minutos de CPU), mas a ADR 0015 registra o gatilho para revisar se o repo
   mudar de visibilidade.
4. **14 dias sem regressão ≠ produto pronto** — o critério mede estabilidade dos
   cenários conhecidos, não a completude. A lista de bugs conhecidos (critério
   3) é o que impede o otimismo: o M3 só fecha com ela publicada.

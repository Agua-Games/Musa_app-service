# ADR 0017 — Hosting de produção: Container Apps (consumption) para a API dinâmica; Pages + R2 seguem

- **Status:** proposta (aguardando aprovação do dono)
- **Data:** 2026-10-12
- **Relacionada:** ADR 0006 (formato do artefato — imagem de contêiner),
  ADR 0009 (object storage — R2), ADR 0015 (emenda: build dirigido por
  evento), `docs/M3_carga.md` (números medidos), `docs/M4_plano.md` fase M4.0

## Contexto

Em produção, três componentes precisam de "lugar para morar":

1. **Site estático do museu** — já resolvido: GitHub Pages (grátis, domínio
   customizado com SSL grátis). O público navega aqui.
2. **Assets (fotos, GLBs)** — já resolvido: Cloudflare R2, egress zero
   (ADR 0009).
3. **API dinâmica (`musa_build serve`)** — admin do curador + assistente. É o
   **único** componente que precisa de compute hospedado, e é sobre ele que
   esta ADR decide.

O padrão de uso da API dinâmica é decisivo: **rajadas**. O público nunca toca
o contêiner (lê o site estático); quem toca é o curador em sessões de edição
(minutos por dia) e o assistente (consultas pontuais). Números MEDIDOS no
M3.5 (máquina do estúdio, 2026-10-12): startup do serve **1,7 s constante**;
**3,9 MB de RAM marginais** por museu de 500 itens; `/items` p95 ≤ 16 ms e
`/search` p95 235 ms mesmo em 10.000 itens; build linear (~1,7 ms/item).

A emenda da ADR 0015 fixou a direção **"dirty → rebuild"**: a escrita na API
marca o tenant como sujo e um worker reage reconstruindo/publicando — nada de
builds agendados. O worker de rebuild cavalgueia a escolha desta ADR
(Container Apps *jobs* ou o `deploy.yml` do repo do cliente, que já reage a
push hoje).

## Decisão proposta

1. **Azure Container Apps (plano consumption) para a API dinâmica.** O grant
   mensal gratuito (180 mil vCPU·s + 360 mil GiB·s + 2 mi de requests, por
   assinatura — fonte: página oficial de preços da Azure, out/2026) cobre a
   fase de MVP com folga, e o **scale-to-zero** casa com o padrão de rajadas:
   museu sem curador ativo = contêiner zerado = custo zero. Cold start é o
   startup medido (1,7 s) + pull da imagem — aceitável para o admin, que é
   quem usa; o público nunca espera contêiner.
2. **Site estático permanece no GitHub Pages** (grátis, já funciona, domínio
   do cliente com SSL grátis) e **assets permanecem no R2** (ADR 0009). A
   arquitetura de três camadas não muda — só ganha onde o contêiner roda.
3. **Domínios**: cada museu aponta seu domínio próprio para o Pages (ex.:
   `museu.com.br`); a API dinâmica responde em subdomínio nosso
   (`api-<museu>.musa.app` ou similar — Container Apps suporta domínio
   customizado com certificado gerenciado). Registro de marca `musa.app`
   (ou equivalente) entra na checklist do M4.8.
4. **Gatilho de revisão registrado**: migrar para **App Service B1**
   (~US$ 12–13/mês — um plano hospeda dezenas de museus, pois a cobrança é
   por plano, não por app) quando qualquer uma ocorrer: (a) grant gratuito
   estourando por 2 meses seguidos; (b) feature pública sensível a cold start
   (ex.: assistente embutido na página pública em produção); (c) necessidade
   de Always On comprovada por métrica, não por intuição.

## Alternativas consideradas

| Alternativa | Por que não (agora) |
|---|---|
| **App Service B1 desde já** | US$ 12–13/mês recorrentes antes do primeiro cliente pagante — exatamente o que o dono proibiu na fase atual; o Always On não é necessário enquanto o público só lê o site estático. Fica como destino documentado do gatilho de revisão |
| **App Service F1 (Free)** | 60 min de CPU/dia, sem Always On, sem SSL em domínio customizado — o site dorme e a demo a investidor quebraria; serve para spike técnico, não para produção |
| **Tudo na Azure (site + assets + API)** | Consolidação de fornecedor já foi analisada na ADR 0009 e rejeitada por custo (egress do Blob); Pages + R2 são grátis e funcionam hoje |
| **VM barata (B1s) com Docker** | Vira servidor para administrar (patch, reboot, certificado, monitoramento) — o estúdio não quer operar VM; managed container é mais barato em horas humanas |
| **Cloudflare Workers/Containers para a API** | A imagem é Python/FastAPI stateful (overlay SQLite); Workers exigiria reescrever o runtime. O R2 continua nos assets — só o compute vai para a Azure |

## Tabela de custo por cenário (ESTIMATIVA — preços de tabela out/2026, confirmar no portal antes de contratar)

| Cenário | Container Apps (consumption) | App Service B1 | Site (Pages) | Assets (R2) |
|---|---|---|---|---|
| 1 museu (500 peças) | **≈ US$ 0** (dentro do grant) | US$ 12–13 | US$ 0 | centavos (M3.5 §3) |
| 10 museus | **≈ US$ 0–2** (grant cobre ~12× o uso típico estimado) | US$ 12–13 (um plano) | US$ 0 | centavos cada |
| 50 museus | **US$ 5–15** (grant estoura; cobrança por segundo) | US$ 12–13 (um plano; vigiar CPU compartilhada) | US$ 0 | ~R$ 0,10–1,00 cada |

Pressupostos da estimativa: 20 sessões de admin/mês por museu × 5 min ×
0,25 vCPU; assistente ~2 mil consultas/mês por museu. RAM medida: 50 × 3,9 MB
≈ 195 MB ≪ 1,75 GB do B1. **Custo marginal por cliente fica abaixo de
R$ 5/mês em qualquer cenário — alimenta a precificação por tier (M4.0/M4.7).**

## Consequências

- **Custo de produção na fase MVP: ≈ R$ 0/mês** até o gatilho de revisão —
  coerente com a regra do dono (nenhuma subscription nova antes de cliente).
- A imagem `ghcr.io/agua-games/musa-app` (ADR 0006) é o artefato que o
  Container Apps executa — nenhuma mudança de distribuição.
- Lock-in mitigado: é uma imagem OCI rodando FastAPI; migrar para App Service,
  VM ou outro provedor é mudar o deploy, não o código.
- Risco aceito: cold start de ~2–4 s na primeira requisição após idle —
  mitigado pelo fato de quem espera ser o admin, não o público; se virar
  problema medido, o gatilho (b) leva ao B1.
- O grant gratuito é **por assinatura** — a nota do HANDOFF se aplica: a conta
  Azure de produção será da empresa do Musa (ou debitada ao cliente), não do
  cartão pessoal; checar antes de provisionar no M4.8.

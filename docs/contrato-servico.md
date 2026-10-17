# Minuta — Contrato de Prestação de Serviços MUSA (app-service para museus)

> **STATUS: MINUTA DE TRABALHO (2026-10-17) — NÃO ASSINAR.**
> Documento-base para revisão de assessoria jurídica antes de qualquer uso
> comercial. Os pontos que exigem decisão legal ou comercial estão marcados
> com **[A DEFINIR]**. Todos os números técnicos citados são os medidos e
> documentados em `docs/M3_slos.md` — nenhum alvo sem evidência.

---

## 1. Partes e objeto

**CONTRATADA:** [razão social da empresa MUSA, CNPJ — A DEFINIR], doravante
"Plataforma".

**CONTRATANTE:** [razão social do museu/instituição, CNPJ], doravante
"Museu".

**Objeto:** licenciamento de uso do serviço MUSA ("Software as a Service")
que transforma o acervo do Museu — mantido em repositório de conteúdo do
próprio Museu — em um site público (acervo digital, visualizações 3D,
gêmeo digital, cinema de arte, loja e demais módulos contratados),
incluindo operação, atualizações da aplicação e suporte, na forma do
plano e dos módulos adicionais escolhidos (Anexo I).

1.1. O serviço é de **licenciamento e operação de software**; não há
transferência de titularidade do código-fonte da Plataforma, nem cessão
do acervo do Museu à Plataforma.

## 2. Definições

- **Acervo Digital:** obras, fichas técnicas (cards), imagens, modelos 3D,
  textos e demais conteúdos fornecidos ou aprovados pelo Museu.
- **Repositório do Cliente:** repositório Git (GitHub) titulado pelo
  Museu, que armazena o Acervo Digital em formato aberto documentado
  (esquema de card, `schemas/card/v1`).
- **Artefato:** imagem de contêiner versionada da aplicação
  (`ghcr.io/agua-games/musa-app:<versão>`), distribuída com notas de
  versão (GitHub Releases).
- **Overlay:** banco de dados operacional com as edições feitas pelo
  painel de administração entre publicações.
- **Entitlement:** arquivo assinado criptograficamente (Ed25519) que
  registra plano, módulos e validade do licenciamento.

## 3. Planos, módulos e preços

Valores vigentes (Anexo I — espelho do `plans.json` publicado):

| Plano | Mensalidade |
|---|---|
| Bronze — Museu Digital | R$ 597 |
| Silver — Museu Interativo | R$ 1.197 |
| Gold — Museu Imersivo | R$ 3.197 |

Módulos adicionais (mensalidade por módulo): Assistente virtual R$ 249 ·
Displays interativos R$ 300 · Streaming de cinema de arte R$ 400 ·
Gêmeo digital — itens adicionais R$ 90/item · Gêmeo digital — áreas
adicionais R$ 650/área · Loja R$ 180 · API de exportação R$ 400 ·
Camada multilíngue R$ 150.

3.1. **Upgrade e downgrade** têm efeito imediato mediante reemissão do
entitlement; a cobrança é proporcional [regra de pro-rata — A DEFINIR].
3.2. **Reajuste:** anual por [IPCA/IGP-M — A DEFINIR], com aviso prévio
de 90 dias; novos preços valem na renovação seguinte.
3.3. **Infraestrutura de terceiros** (Cloudflare, GitHub, provedor de
IA): nesta fase, contratada e paga diretamente pelo Museu em conta
própria, a critério do Museu [decisão vigente do estúdio — minimiza
repasse tributário; cláusula alternativa "incluso no serviço" — A DEFINIR].
3.4. Inadimplência > [30] dias: ver §8 (suspensão).

## 4. Propriedade intelectual

| Material | Titular |
|---|---|
| Aplicação MUSA (código, builder, design do frontend, documentação técnica) | **Plataforma** |
| Acervo Digital (fichas, fotos, modelos 3D, textos) | **Museu** |
| Direitos sobre as obras retratadas | Museu ou terceiros — o Museu declara ter os direitos/autorizações (ver §4.2) |
| Adaptações/contribuições feitas pela Plataforma a pedido do Museu sobre o Acervo Digital | Museu [A DEFINIR: cessão integral vs. licença] |
| Melhorias genéricas da aplicação decorrentes de demandas do Museu | Plataforma |

4.1. A Plataforma recebe do Museu **licença não exclusiva, revogável na
rescisão e limitada à finalidade** de operar o serviço sobre o Acervo
Digital (hospedar, processar, exibir publicamente no site do Museu).
4.2. O Museu garante deter os direitos ou licenças (ex.: CC0, domínio
público, autorização do artista) sobre todo material que cadastrar; o
contrato de card registra `licenca` e `fonte` por item, exibidos
publicamente no site.
4.3. Documento de IP interno da Plataforma (o que é da plataforma, do
cliente e de colaboradores): pendente — ver HANDOFF §Comercial.

## 5. Níveis de serviço (SLA)

Princípio: **nenhum alvo sem número medido** (`docs/M3_slos.md`). Os SLOs
abaixo são os contratuais propostos; os marcados como "(provedor)" são
repassados do SLA do fornecedor de infraestrutura.

| Métrica | SLO contratual | Evidência medida |
|---|---|---|
| Disponibilidade do site público | 99,9% mensal (provedor: GitHub Pages/Cloudflare) | repasse do SLA do provedor |
| Latência p95 de leitura da API | < 300 ms | 16 ms @ 10.000 itens (2026-10-12) |
| Latência p95 de busca | < 500 ms em acervos até 10.000 itens | 235 ms @ 10.000 (2026-10-12) |
| Publicação fim-a-fim (push → no ar) | < 2 min | mediana 36 s (2026-10) |
| Build do acervo | < 10 min / 1.000 peças | 2,2 s / 1.000 (2026-10-12) |
| RPO (perda máxima de dados) | 0 para o acervo versionado; edições do painel até o último backup/commit | ADR 0003; runbook §backup |
| RTO (restauração) | < 5 min para redeploy; overlay: conforme backup | DR drill cronometrado (M4.4) |

5.1. **Créditos de serviço:** indisponibilidade mensal abaixo do alvo por
falha da Plataforma gera crédito de [10%] da mensalidade por faixa de
[x] horas, limitado a [100%] da mensalidade [percentuais — A DEFINIR].
5.2. **Exclusões:** indisponibilidade do provedor de infra (GitHub,
Cloudflare, Azure), força maior, manutenção programada avisada com 72 h,
e falhas causadas por conteúdo do Museu rejeitado pelo gate de contrato.
5.3. **Suporte:** canal [e-mail/painel — A DEFINIR]; resposta em até
[1 dia útil] para incidentes críticos (site fora do ar), [3 dias úteis]
demais assuntos.

## 6. Proteção de dados (LGPD)

6.1. **Papéis:** o **Museu é o controlador** dos dados pessoais tratados
no serviço; a **Plataforma é a operadora**. (Registra o pendente do
inventário LGPD, `docs/lgpd.md`.)
6.2. **Suboperadores atuais:** DeepSeek (LLM do assistente — só o texto
da pergunta, sem identificadores), Cloudflare (mídia R2 + Turnstile),
GitHub (hospedagem). Novos suboperadores serão comunicados com 30 dias
de antecedência, com direito de objeção fundamentada.
6.3. A Plataforma não vende, não cede e não usa os dados para finalidade
alheia ao contrato; perguntas ao assistente não são gravadas em log.
6.4. Incidentes de segurança com dados pessoais: notificação ao Museu em
até [48 h — A DEFINIR] com informações da ANPD aplicáveis.
6.5. **Antes da ativação de módulos novos** que tratem dados pessoais
(loja com checkout, analytics, quiosque de áudio), o inventário LGPD é
reaberto e um aditivo é firmado — condição de go-live.

## 7. Portabilidade e saída

7.1. **O Acervo Digital é do Museu e viaja com ele:** o Repositório do
Cliente permanece na titularidade do Museu durante e após o contrato.
7.2. **Formato aberto:** o esquema do card é público e versionado
(`schemas/card/v1`, política de compatibilidade em `COMPATIBILITY.md`) —
o acervo não depende de formato proprietário para ser lido por outra
ferramenta.
7.3. **Exportação:** a qualquer tempo, o Museu pode exportar integralmente
o acervo (JSON por item + mídia original no bucket), sem custo adicional
[plano Gold inclui exportação permanente para arquivamento; API de
exportação é módulo adicional nos demais — confirmar política].
7.4. **Na rescisão:** a Plataforma mantém a exportação disponível por
[90] dias e elimina os dados operacionais remanescentes (overlay, logs)
em até [30] dias após esse prazo, com termo de exclusão.
7.5. **Sem fidelidade** [A DEFINIR: fidelidade mínima de 12 meses em
troca de desconto?]; rescisão imotivada pelo Museu com aviso de 30 dias.

## 8. Suspensão e rescisão por inadimplência

8.1. O entitlement tem validade e é renovado a cada ciclo de cobrança
quitado. Inadimplido o ciclo e vencido o entitlement, **o site sai do ar
automaticamente** — efeito técnico do licenciamento, não ato discricionário.
8.2. O Acervo Digital do Museu **nunca é retido como garantia**: o
Repositório do Cliente permanece acessível ao Museu mesmo suspenso o
serviço (§7.2).
8.3. Tolerância de [15] dias com aviso antes da não-renovação do
entitlement [A DEFINIR].

## 9. Responsabilidades e limitações

9.1. A Plataforma não responde por: conteúdo cadastrado pelo Museu
(incluídas infrações autorais de itens sem licença declarada), uso
indevido das credenciais pelo pessoal do Museu, e indisponibilidades de
provedores terceiros (§5.2).
9.2. Limite agregado de responsabilidade: [12] mensalidades [A DEFINIR].
9.3. O assistente virtual (IA) pode errar; respostas têm caráter
informativo e citam a ficha da peça como fonte. O Museu pode desativar o
módulo a qualquer tempo.

## 10. Vigência e foro

Vigência indeterminada a partir da assinatura; foro da comarca de
[A DEFINIR], com renúncia a qualquer outro.

## Anexos

- **Anexo I** — Tabela de planos e módulos (espelho do `plans.json`
  vigente; atualizações de preço seguem §3.2).
- **Anexo II** — SLA detalhado e créditos (§5).
- **Anexo III** — Termo de operador LGPD (papéis, suboperadores,
  segurança — base em `docs/lgpd.md`).
- **Anexo IV** — Procedimentos operacionais (runbook de onboarding,
  incidentes e rollback, `docs/runbook.md`).

---

### Checklist para a assessoria jurídica

- [ ] Natureza do contrato (licenciamento SaaS) e enquadramento tributário
      da mensalidade vs. repasse de infraestrutura (§3.3).
- [ ] Regra de pro-rata em upgrade/downgrade (§3.1) e reajuste (§3.2).
- [ ] Percentuais e teto dos créditos de SLA (§5.1) — compatíveis com a
      margem dos tiers (`docs/M4_custos.md`).
- [ ] Cessão vs. licença das adaptações feitas a pedido (§4, última linha).
- [ ] Prazos de notificação de incidente (§6.4) alinhados à ANPD.
- [ ] Fidelidade/desconto (§7.5) e tolerância de inadimplência (§8.3).
- [ ] Limite de responsabilidade (§9.2) e foro (§10).
- [ ] Versão em inglês para clientes estrangeiros (após fechar a PT).

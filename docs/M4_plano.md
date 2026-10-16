# M4 — Plano de ataque: Produção / apresentável

> **Objetivo (HANDOFF):** vender, entregar e não quebrar.
> Data do plano: 2026-10-12. Pré-requisitos cumpridos: M0–M3.6 (M3.7 depende de
> cliente real — não bloqueia o M4, corre em paralelo quando aparecer).

## Resposta de custo, antes de tudo

**Azure não precisa ser pago agora.** O M4 foi desenhado para isso:

- **Tudo até a M4.8 é código, teste e documentação** — roda local ou no CI que
  já existe (GitHub Actions/gratuito), custo R$ 0.
- **M4.8 (deploy de produção) é o único portão pago** e fica **bloqueado até o
  primeiro cliente fechar** — mesma lógica da M3.7. Naquele momento:
  - *App Service B1* ≈ US$ 12–13/mês (preço de tabela aproximado, ago/2026 —
    confirmar no portal antes de contratar): Always On, domínio customizado,
    1,75 GB RAM. Pelos números MEDIDOS do M3.5 (3,9 MB/museu de 500 itens),
    **um único plano B1 hospeda dezenas de museus** — o custo por cliente é
    diluído, não multiplicado.
  - Alternativa a avaliar na M4.0: **Container Apps (consumption)** — grant
    mensal gratuito de 180 mil vCPU-s + 360 mil GiB-s + 2 mi requests, com
    scale-to-zero: para a fase de MVP com poucos museus e tráfego irregular,
    pode sair por centavos ou zero (fonte: página oficial de preços da Azure).
  - Conta Azure nova tem **US$ 200 de crédito / 30 dias** — útil para a
    prova de fogo do M4.8 sem custo, se ainda estiver disponível.
- **F1 (Free) do App Service existe mas não serve para demo**: 60 min de
  CPU/dia, sem Always On, sem SSL em domínio customizado — o site dorme e a
  primeira carga é lenta. Vale para spike técnico, não para investidor.

## Restrições herdadas (valem aqui também)

1. Personas/ambientes em standby até cliente real — nada agendado que gaste
   Cloudflare (emenda ADR 0015).
2. Credenciais por variável de ambiente/secret, nunca no repo.
3. Conta Cloudflare atual é pessoal e temporária (nota no HANDOFF) — checar
   antes de qualquer implementação que mova megabytes.
4. Docs em PT, código/commits em EN. Testes antes de push.

## Fases

### M4.0 — Decisão de hosting (ADR 0017)

> **Estado (2026-10-12): CONCLUÍDA — ADR 0017 aceita pelo dono.** Container
> Apps (consumption) para a API dinâmica; site no Pages e assets no R2 sem
> mudança; gatilho registrado para o App Service B1.

Decidir por escrito, com os números do M3.5: **App Service (B1)** vs.
**Container Apps (consumption)** vs. híbrido (API no Container Apps + site
estático no Pages/R2). Inclui estratégia de domínio: `musa.app` + subdomínio
por museu (wildcard) vs. domínio do cliente; e onde mora o site estático em
produção (Pages continua? ou tudo no Azure?).

**Verificação:** ADR 0017 aceita pelo dono, com tabela de custo/mês por
cenário (1 / 10 / 50 museus) usando os MEDIDOS do M3.5.

### M4.1 — Hardening da imagem de produção

> **Estado (2026-10-12): IMPLEMENTADO — verificação no próximo release.**
> Dockerfile: usuário `musa` não-root (uid 1000, padrão do runtime — CI de
> cliente usa `--user root` explícito para escrever no workspace montado),
> `PYTHONDONTWRITEBYTECODE=1` + `PYTHONUNBUFFERED=1` (raiz read-only), 
> HEALTHCHECK no `/health`, graceful shutdown via uvicorn (PID 1). O release
> pipeline ganhou **portão de fumaça**: a suíte beta inteira roda DENTRO da
> imagem recém-construída com `--read-only --tmpfs /tmp` antes do push —
> imagem que não prova o hardening não é publicada. Guard test em
> `builder/tests/test_image_hardening.py` trava as invariantes declarativas.

Hoje a imagem é de CI/demo. Para produção: usuário não-root, filesystem
read-only onde possível, limites de recursos declarados, healthcheck formal
(`/health` já existe), logs estruturados com nível por ambiente (já existe —
formalizar), graceful shutdown do uvicorn.

**Verificação:** imagem `0.5.0-rc` sobe com FS read-only e usuário sem
privilégio; suíte beta inteira verde contra ela dentro do contêiner.

### M4.2 — Anti-abuso do assistente (server-side)

A preocupação do dono (2026-10-08) virada em código, sempre **server-side** —
a chave do LLM nunca sai do nosso backend:

1. Rate limit por IP/sessão no endpoint de chat.
2. Cota de tokens por museu/dia com **circuit breaker** (estourou → mensagem
   educada, não fumaça).
3. Cloudflare **Turnstile** (gratuito) no endpoint de chat.
4. **Grounding rígido**: o assistente só responde com o acervo recuperado;
   off-topic é recusado por construção do prompt + validação.
5. Telemetria de custo por tenant com alerta de anomalia.

**Verificação:** cenários novos no `beta/misuse.py`: bot martelando o chat
(429 após N), cota diária estourada (circuit breaker abre e registra), pergunta
off-topic recusada. Custos simulados, sem chamada real ao provedor no CI.

> **M4.2 CONCLUÍDA (2026-10-16).** Implementação:
>
> - **Endpoint novo** `POST /assistant/ask` (`builder/musa_build/serve.py`) —
>   o frontend já o esperava (`source/assets/js/api.js`); resposta
>   `{answer, suggestedArtifacts}` sem envelope. Gate de módulo: museu sem
>   `assistant` nos entitlements recebe **404** (stealth, como o gate de
>   conteúdo). `ServeState` ganhou o campo `modules`.
> - **Stack anti-abuso** em `builder/musa_build/assistant.py`, da camada mais
>   barata à mais cara: Turnstile (só com `MUSA_TURNSTILE_SECRET`; fail-closed)
>   → rate limit por IP (`MUSA_ASSISTANT_RPM`, padrão 10/min, janela deslizante)
>   → respostas prontas (saudação, visão geral do acervo — custo zero) →
>   **filtro off-topic** (pergunta sem nenhum token no índice público é
>   recusada **sem chamar o provedor** — a proteção de custo mais forte;
>   stopwords PT/EN nunca contam como evidência) → cota diária de tokens
>   (`MUSA_ASSISTANT_DAILY_TOKENS`, padrão 200 mil/dia UTC) → circuit breaker
>   de provedor (5 falhas seguidas abrem por 5 min, 503 sem chamar o provedor).
> - **Grounding**: o provedor só vê as fichas públicas recuperadas do índice +
>   system prompt que descreve os campos do card e proíbe inventar além delas
>   (mesma regra "contexto antes de conteúdo" do pipeline OCR, M2.6).
> - **Provedor**: `DeepSeekClient` (`DEEPSEEK_API_KEY`, modelo via
>   `MUSA_DEEPSEEK_MODEL`, padrão `deepseek-chat`) ou `FakeLLMClient`
>   determinístico (`MUSA_LLM_FAKE=1` — dev/testes/beta, custo ~zero).
> - **Telemetria**: todo ask loga `assistant_ask` com outcome, tokens,
>   cache-hit, `cost_usd_estimate` (tabela off-peak DeepSeek, ver
>   `docs/M4_custos.md`) e **hash do IP** (nunca o IP cru — LGPD).
> - **Divisão de verificação decidida**: rate limit e off-topic vão ao
>   `beta/misuse.py` (cenários 11 e 12, este último por último para a janela
>   de rate limit não contaminar os demais); cota, breaker e Turnstile ficam
>   nos testes unitários (`builder/tests/test_assistant.py`, 21 testes) —
>   o misuse não controla env por cenário.
> - Suítes: builder 133 verdes, beta 15 verdes. API reference regenerada
>   (seção "Assistente (M4.2)").

### M4.3 — Segurança auditável

1. **Auditoria de gating como artefato**: script que prova, com saída legível
   para não-técnico, que um museu Bronze não recebe 1 byte do Gold (reusa os
   invariantes do M3.3; gera relatório anexável a contrato).
2. Rate limits na API de escrita (hoje: sem limite).
3. Entitlements: imagem de release **exige assinatura** (o modo dev-unsigned já
   imprime warning — vira erro em imagem tagueada).
4. Um token por tenant já existe (M1.4); formalizar rotação no runbook.

**Verificação:** relatório de auditoria gerado contra o DemoMuseum; teste que
a imagem de release rejeita entitlements não assinados.

> **M4.3 CONCLUÍDA (2026-10-16).** Implementação:
>
> - **`musa-build audit`** (`builder/musa_build/audit.py`): sobe o app real
>   in-process (TestClient) e sonda a superfície pública HTTP — 6 verificações:
>   contrato válido item a item, rascunhos invisíveis (JSON **e** arquivos),
>   nada acima do tier (itens, arquivos e coleções), **controle positivo**
>   (com token o rascunho aparece — prova que o 404 é decisão do portão, não
>   dado faltando — e o tier não relaxa nem para admin), busca limpa e
>   `card.json` não baixável. Relatório em PT claro (`render_markdown`),
>   anexável a contrato, com nota honesta quando a prova de tier é vacuosa
>   (museu gold). Exit 1 em qualquer vazamento.
> - **Relatório real gerado**: `docs/auditoria-gating-demo-museum.md` —
>   DemoMuseum APROVADO, 1071 sondas (321 públicos válidos, 143 rascunhos
>   invisíveis).
> - **Rate limits por IP** (`MUSA_WRITE_RPM` padrão 60/min em POST /items e
>   /collections; `MUSA_LOGIN_RPM` padrão 5/min em /auth/login — o alvo de
>   brute force do token do tenant; 0 desliga, para o harness de carga).
>   O limiter é o mesmo `RateLimiter` da M4.2; 429 com `Retry-After`.
> - **Release exige assinatura**: `MUSA_REQUIRE_SIGNED_ENTITLEMENTS=1` no
>   Dockerfile da imagem — pin dev não-assinado vira erro ali (fecha o buraco
>   de auto-promoção via `musa: 0.0.0-unreleased`). O smoke gate do release
>   desliga só para o fixture (dev-pin por desenho). Dev local no código-fonte
>   mantém o warning.
> - **Runbook semeado**: `docs/runbook.md` com rotação de todas as
>   credenciais (admin token, DeepSeek, Turnstile, R2 — com a pendência do
>   secret exposto —, Ed25519, GHCR PAT); M4.4 expande.
> - Testes: +15 (audit 6, write limits 6, entitlements 3). Achado de teste:
>   limiter in-memory vaza entre métodos de uma classe unittest — app por
>   método, não por classe.

### M4.4 — Operação: backup, DR e runbook

1. **Backup local** do overlay `.musa/` (pendência assumida na M3.6: RPO do
   overlay hoje é "até o próximo commit") + **restore ensaiado e cronometrado**
   (DR drill de verdade: apaga tudo, restaura, mede).
2. **Runbook**: onboarding de cliente novo, resposta a incidente, rollback de
   versão da imagem (pin no `museum.config.json` já permite — documentar).
3. **Alertas dos SLOs do M3.6** (spec §8.2, hoje pendente): gatilhos de build
   quebrado, ficha rejeitada, egress acima da faixa; canal de notificação.

**Verificação:** ata do DR drill com tempos medidos (meta: RTO < 5 min, do
SLO proposto); runbook revisado executando-o de ponta a ponta.

### M4.5 — Bateria final de testes do MVP (portão de saída)

O pedido do dono (2026-10-11), já enumerado no HANDOFF §M4: edge cases de
contrato (unicode/RTL, `data_iso` BCE, campos vazios vs. ausentes), gating
(draft órfão, hero despublicado, coleção vazia), concorrência (N escritores
com/sem `_rev`, escrita durante build), infra (overlay corrompido, disco
quase cheio, CI sem secrets), pipeline (LLM fora do ar, JSON quebrado), carga
(10k itens, capa de 20 MB) e navegador (JS bloqueado, 3G, primeiro acesso).
Rodada sobre a **imagem publicada**, estendendo o harness do `beta/`.

**Verificação:** cada edge case com veredito; divergências viram issue ou
correção; bateria integrada ao `beta-validation.yml` como suíte `edge`.

### M4.6 — LGPD + licenças

1. Dados de visitante (analytics?), áudio de quiosque, retenção e exclusão —
   inventário do que coletamos (hoje: praticamente nada; documentar é 80% do
   trabalho) + página de privacidade modelo para o cliente adaptar.
2. Créditos e licenças de todo asset público exibidos (o DemoMuseum já usa
   domínio público/CC — conferir a renderização dos créditos).

**Verificação:** doc `docs/lgpd.md` + checklist de conformidade por cliente;
tela do demo mostrando créditos.

### M4.7 — Ambiente de demonstração

**3 museus fictícios, um por tier** (Bronze/Silver/Gold), com narrativa de
upgrade — é o que se mostra a investidor e cliente. Acessibilidade WCAG AA e
multi-idioma (spec: já é requisito; aqui vira verificação formal).

**Verificação:** narrativa roteirizada de 5 minutos executada de ponta a ponta
(criar conta → publicar peça → upgrade de tier → recurso Gold aparece);
checklist WCAG AA varrido na landing e no acervo.

### M4.8 — Deploy de produção ⛔ **PORTÃO PAGO — bloqueado até o 1º cliente**

Só começa com cliente fechado (decisão do dono, 2026-10-12). Provisionar o
hosting decidido na M4.0, domínio + SSL, CI/CD de produção, alertas ligados,
backup do overlay agendado. Estimativa de esforço: 1–2 dias, porque tudo até
aqui já deixou a infra ensaiada.

**Verificação:** primeiro cliente no ar pelo runbook do M4.4, sem nenhum passo
"de desenvolvedor"; SLOs do M3.6 reportando.

## Critérios de saída do M4 (do HANDOFF, com a fase que os prova)

| Critério | Fase |
|---|---|
| Gating auditável (Bronze não recebe Gold — teste, não promessa) | M4.3 |
| Anti-abuso do assistente em camadas, server-side | M4.2 |
| LGPD documentada + créditos de assets | M4.6 |
| Backup local + restore ensaiado e cronometrado | M4.4 |
| Runbook (onboarding, incidentes, rollback) | M4.4 |
| Bateria final de edge cases sobre a imagem publicada | M4.5 |
| WCAG AA + multi-idioma | M4.7 |
| Ambiente demo com 3 museus e narrativa de upgrade | M4.7 |
| Custo por cliente/mês conhecido, dentro da margem | M4.0 + M3.5 |
| Primeiro cliente em produção | M4.8 ⛔ pago |

## Ordem e dependências

```
M4.0 (decisão) ──► M4.1 (imagem) ──► M4.4 (operação) ──► M4.7 (demo)
                     │                                        │
M4.2 (anti-abuso) ──►├─► M4.3 (auditoria) ──► M4.5 (bateria) ▼
                                                   M4.8 ⛔ (pago, com cliente)
```

M4.6 (LGPD) é paralela e barata. M4.5 é o portão de saída: nada vai para
produção sem ela verde.

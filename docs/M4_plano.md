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

> **M4.4 CONCLUÍDA (2026-10-16).** Implementação:
>
> - **Backup/restore do overlay** (`builder/musa_build/backup.py` +
>   `musa-build backup|restore`): cópia consistente pela backup API do
>   SQLite (segura com o serve vivo), manifest com museum_id, contagens e
>   sha256; restore recusa museum errado ou cópia corrompida **antes** de
>   escrever, preserva o overlay atual em `state.before-restore-<ts>` e
>   boot-prova o app no final — restore que não boota é falha, não sucesso.
>   Fecha a pendência de RPO assumida na M3.6.
> - **DR drill cronometrado** (`tools/dr_drill.py`, executado contra o
>   DemoMuseum real): edita 3 registros só no overlay, backup, cópia
>   "off-site", T0 (mata serve, apaga repo + overlay), re-clone + restore +
>   boot + verificação. **RTO medido 4,5 s vs meta 300 s**; payload público
>   byte-idêntico (322 itens). Ata em `docs/dr-drill-ata.md`, com limites
>   honestos (repo pequeno, rede local, mídia no R2 fora do drill).
> - **Alertas dos SLOs** (`builder/musa_build/alerts.py` +
>   `tools/check_alerts.py`): 5 regras por dia UTC sobre o JSONL do serve —
>   custo-assistente, cota-estourada, cards-rejeitados (422), egress-assets
>   (404 não conta), qualquer-5xx. Limiares como argumentos (pontos de
>   partida por tenant, não SLO contratual). Exit 1 = alerta, pronto para
>   scheduler; canais documentados no runbook (CI vermelho + e-mail do
>   Actions para build; check agendado para runtime; Azure Monitor na M4.8).
> - **Runbook completo** (`docs/runbook.md`): onboarding de cliente em 10
>   passos (marcando os que são só do dono), 4 cenários de incidente,
>   rollback como re-pin de tag imutável, tabela dos 5 alertas com ações,
>   operação de backup/restore com retenção sugerida e ensaio mensal.
> - Testes: +13 (backup 6 — round-trip byte-idêntico incluso; alertas 7).

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

> **M4.5 CONCLUÍDA (2026-10-17).** Implementação:
>
> - **`beta/edge.py` — 24 casos com veredito individual**, rodados contra o
>   DemoMuseum real (run `20261017T023351Z-seed42`: **23 passa + 1 gap
>   conhecido, 0 falhas**, linha vermelha intacta — acervo pré-existente
>   byte-idêntico após a bateria):
>   - *contrato* (5): unicode/emoji/RTL round-trip byte-idêntico + busca;
>     `asset_id` de 120 chars aceito (sem limite de tamanho em contrato nem
>     serve — risco de filesystem documentado) e maiúsculo 422 (serve mais
>     estrito que o contrato, a direção segura); vazio-vs-ausente explícito;
>     `data_iso` BCE/ano de 1 dígito aceitos com round-trip exato, mês-13 422;
>     título de coleção com 10k chars aceito sem quebrar nada.
>   - *gating* (5): draft órfão de coleção despublicada 404 público
>     (**gap-orphan-visibility**: invisível também para o admin — gap
>     registrado); hero despublicado nunca fura o portão; coleção vazia
>     publicada listada com count 0; **downgrade/upgrade de tier com reboot**
>     (item do tier some no bronze e volta no gold — prova real no DemoMuseum);
>     **config assinado adulterado derruba o boot com erro explícito de
>     assinatura** (auto-promoção impossível — prova real, ADR 0010).
>   - *concorrência* (4): dois escritores com o mesmo `_rev` → exatamente um
>     200 e um 409; sem `_rev` last-write-wins sem corrupção; 30 patches sob
>     leituras públicas simultâneas sem nenhum 5xx; escrita durante build
>     verde (repo e overlay independentes por arquitetura).
>   - *infra* (4+reboot): serve sem `MUSA_ADMIN_TOKEN` → read-only explícito
>     (503, health "disabled", reads ok); overlay corrompido → boot falha com
>     mensagem apontando o operador (correção abaixo) e overlay apagado →
>     museu reconstruído do seed; build com destino impossível → exit não-zero
>     com mensagem; CI sem secrets → preflight explícito (correção abaixo).
>   - *pipeline/carga/navegador*: duplicata de `asset_id` 409 (regressão do
>     guard M3.2); build com asset local de 20 MB verde (5,7 s vs 5,8 s
>     baseline); payload de primeiro acesso 2.702 KB local (vídeo hero no
>     YouTube, mídia no R2); catálogo renderiza de dados locais com CDN
>     bloqueado (só os viewers 3D degradam); primeiro acesso sem conta —
>     login vive no modal admin, nunca bloqueia o conteúdo primário.
>     Cobertos por suítes existentes (não duplicados): LLM fora/JSON quebrado
>     (M4.2 `test_assistant*`), 10k itens (M3.5 `beta/load.py`).
> - **`beta/harness.py`**: ciclo de vida do serve extraído do runner —
>   reboot com env/config mutados, stderr em arquivo (boot quebrado é
>   diagnosticável), health-wait sai cedo se o processo morreu. Rate limits
>   desligados no harness (determinismo; M4.3 cobre os limites).
> - **Divergências encontradas e corrigidas**: (1) CI do cliente sem
>   `GHCR_PULL_TOKEN` falhava com erro críptico de docker login → step
>   **Preflight** no `deploy.yml` do DemoMuseum (template dos clientes);
>   (2) overlay corrompido derrubava o boot com traceback cru **e deixava a
>   conexão SQLite aberta** (arquivo travado no Windows) → `StoreError` com
>   o caminho do operador + conexão fechada antes de levantar (+2 testes).
> - **Integração**: `--suite edge` no `run_beta` (`all` inclui); choice
>   `edge` no `beta-validation.yml` do DemoMuseum — **manual-only, sem cron**
>   (decisão do dono 2026-10-16: rotinas agendadas só com cliente pagante;
>   no CI da imagem fica disponível a partir do artifact 0.5.0).
> - Testes: +5 (edge battery 3 contra o fixture — aceitação de cada caso;
>   store 2). A bateria inteira roda em ~65 s no fixture.

### M4.6 — LGPD + licenças

1. Dados de visitante (analytics?), áudio de quiosque, retenção e exclusão —
   inventário do que coletamos (hoje: praticamente nada; documentar é 80% do
   trabalho) + página de privacidade modelo para o cliente adaptar.
2. Créditos e licenças de todo asset público exibidos (o DemoMuseum já usa
   domínio público/CC — conferir a renderização dos créditos).

**Verificação:** doc `docs/lgpd.md` + checklist de conformidade por cliente;
tela do demo mostrando créditos.

> **M4.6 CONCLUÍDA (2026-10-17).** Implementação:
>
> - **Inventário LGPD** (`docs/lgpd.md`): a arquitetura é a principal medida
>   de conformidade — sem contas de visitante, sem cookies, sem analytics.
>   Tabela dado-a-dado: a pergunta do assistente vai à DeepSeek **sem
>   identificadores e nunca é gravada**; o IP existe só como hash SHA-256
>   truncado (pseudonimizado) e em memória para rate limit; logs operacionais
>   com retenção-alvo de 90 dias via sweep. Bases legais, resposta a direitos
>   dos titulares, suboperadores (DeepSeek/Cloudflare/GitHub) e dados futuros
>   (áudio de quiosque, checkout, analytics → reavaliação obrigatória antes
>   do go-live). Checklist de conformidade por cliente no §5.
> - **Página de privacidade modelo** (`docs/privacidade-modelo.md`): texto em
>   PT pronto para o cliente adaptar ([NOME DO MUSEU], CNPJ, DPO) e publicar.
> - **Contrato 1.2.0** (minor compatível, COMPATIBILITY.md): campos opcionais
>   `licenca` (declaração de direitos) e `fonte` (instituição/URL de origem).
>   Schema empacotado sincronizado; API reference regenerada.
> - **Render no site**: lightbox da peça mostra a linha `licenca · fonte`
>   quando o card os carrega (oculta caso contrário) — verificado em build
>   local: 313 dos 321 itens públicos com licença, `lbRights` no HTML.
> - **Backfill DemoMuseum** (commit `a4336aa`, deploy verde): 450 imports do
>   Met com `CC0 1.0` + URL da peça; 5 pinturas de domínio público
>   (Vermeer, Van Gogh, Monet, Rembrandt) com `Domínio público` + Wikimedia.
>   **Esculturas demo ficaram sem** — atribuições fictícias sem proveniência
>   verificável; preencher é dever do cliente no checklist, não do script.
> - **Ressalva de deploy**: o gate da imagem 0.4.0 (contrato 1.1.0) aceitou
>   os campos novos — minor compatível funcionando como projetado; o **render
>   visual** dos créditos entra no site publicado com o artifact 0.5.0
>   (frontend novo) + re-pin do cliente.
> - Testes: builder 164 verdes (drift do schema + freshness da API reference
>   provam a sincronia 1.2.0).

### M4.7 — Ambiente de demonstração

**3 museus fictícios, um por tier** (Bronze/Silver/Gold), com narrativa de
upgrade — é o que se mostra a investidor e cliente. Acessibilidade WCAG AA e
multi-idioma (spec: já é requisito; aqui vira verificação formal).

**Verificação:** narrativa roteirizada de 5 minutos executada de ponta a ponta
(criar conta → publicar peça → upgrade de tier → recurso Gold aparece);
checklist WCAG AA varrido na landing e no acervo.

> **→ Concluída (2026-10-17)**
> - **3 demos assinados** em `H:\Musa_app-service\demos\` (fora do git da
>   plataforma, como o DemoMuseum): `atelier-bronze`, `galeria-silver`
>   (assistente + Vênus de Milo 3D offline) e `palazzo-gold` (assistente,
>   loja, streaming, sala de exibição), gerados por `tools/make_demos.py`
>   com entitlements Ed25519 reais (expiram 2030). Build validado nos 3.
>   Decisão de custo: GitHub Free tem repos públicos ilimitados e Actions
>   grátis em repo público — demos podem ir ao ar a custo zero quando o
>   dono decidir; repos remotos NÃO foram criados (não autorizado).
> - **Narrativa executável** `tools/demo_narrative.py`: os 5 beats rodam de
>   verdade contra um harness descartável (repo demo intacto, re-executável)
>   — inclui o **upgrade real** (re-assinatura bronze→gold+módulos com a
>   chave da plataforma). RODADA: "NARRATIVA APROVADA" em ~4s. Roteiro
>   humano (o que dizer em cada beat + perguntas prováveis) em
>   `demos/ROTEIRO.md`.
> - **Achado real → correção**: a narrativa reprovou no beat 1 — `/store/products`
>   e `/cinema/programme` não eram gated por módulo no `serve.py` (só o
>   assistente tinha a regra stealth). Corrigido: cinema exige `streaming`
>   ou `screening-room`, loja exige `store`, senão 404; `/plans` segue
>   público por desenho. Regressão coberta em `tests.test_serve`.
> - **WCAG AA**: checklist formal em `docs/wcag.md` — contraste computado
>   pela fórmula oficial, `--paper-faint` corrigido (α 0.38→0.55, piso
>   documentado no CSS), `role="dialog"`+`aria-modal`+rótulos nos 6
>   overlays, `aria-label` nos botões "×" e nos 2 inputs sem label, `alt`
>   dinâmico no admin. Dívidas registradas: ordem de headings (h4 sob h2)
>   e focus trap — nenhuma reprova AA. Multi-idioma documentado como
>   módulo pago não implementado (m-multilingual).

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

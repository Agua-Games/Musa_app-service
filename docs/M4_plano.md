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

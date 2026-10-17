# LGPD no MUSA — inventário, bases legais e checklist por cliente

> Milestone **M4.6** (2026-10-17). O inventário abaixo descreve o que a
> plataforma coleta **hoje** — deliberadamente quase nada: a arquitetura
> (site estático, sem contas de visitante, sem cookies, sem analytics) é a
> principal medida de conformidade. Documentar é 80% do trabalho; os 20%
> restantes são a retenção dos logs operacionais e a página de privacidade
> que cada cliente adapta (`docs/privacidade-modelo.md`).
>
> Este documento não é aconselhamento jurídico: é o mapa técnico honesto
> sobre o qual o jurídico decide.

## 1. Inventário de dados pessoais

### 1.1 Visitante do site (o público do museu)

| Dado | Coletado? | Onde fica | Observação |
|---|---|---|---|
| Conta, nome, e-mail | **Não** | — | Não existe conta de visitante; o site é público e estático |
| Cookies / analytics | **Não** | — | Nenhum cookie, nenhum pixel, nenhum Google Analytics |
| IP no acesso às páginas | Pelo **GitHub Pages** (logs próprios) | GitHub | Controlador: GitHub (DPA próprio); a plataforma não lê esses logs |
| IP no acesso à mídia (R2) | Pela **Cloudflare** (logs próprios) | Cloudflare | Controlador: Cloudflare; a plataforma não lê esses logs |
| Pergunta ao assistente | **Sim, em trânsito** | ver §1.2 | O texto da pergunta **não é gravado em log** |

### 1.2 Assistente de acervo (módulo `assistant`)

Fluxo: visitante digita uma pergunta → o **nosso backend** (`serve`) aplica a
pilha anti-abuso (Turnstile → rate limit → respostas prontas → filtro de
off-topic → cota diária) → só então, se necessário, chama a **DeepSeek**.

| Dado | Tratamento |
|---|---|
| Texto da pergunta | Enviado à DeepSeek **somente** quando nenhuma camada barata responde; **nunca gravado** em log nem em disco; cache em memória (morre com o processo) |
| IP do visitante | Usado em memória para rate limit; nos logs apenas como `ip_hash` = SHA-256 truncado (12 hex) — **pseudonimizado**: sem uma lista externa de IPs não há como reidentificar; o IP **nunca** é enviado à DeepSeek |
| Token Turnstile | Enviado à Cloudflare para verificação de humanidade (sem ele, bots esgotariam a cota de tokens) |
| Telemetria | outcome, tokens in/out, custo estimado — números, sem conteúdo |

**Transferência internacional:** a pergunta vai para a DeepSeek (fora do
Brasil). Base legal: execução de contrato/legítimo interesse com minimização
(sem identificadores, sem histórico). A página de privacidade modelo declara
isso explicitamente (§Transferências).

### 1.3 Curador / equipe do museu (admin)

| Dado | Tratamento |
|---|---|
| Token de admin | Um por tenant (M1.4); rotação no runbook |
| "E-mail" da sessão | **Rótulo livre** digitado no login — não é verificado nem usado para contato; fica no log `auth_login` |
| Edições no acervo | Log `api_write` (ação + asset_id) — dados do acervo, não pessoais |

### 1.4 O que a plataforma registra (log JSONL do serve)

- `api_request`: método, path, status, duração — **sem IP**;
- `assistant_ask`: `ip_hash` (pseudonimizado), outcome, tokens, custo — **sem o texto da pergunta**;
- `auth_login`: o rótulo de e-mail;
- `api_write`: ação e asset.

**Retenção:** os logs são operacionais e locais. Recomendação padrão:
**90 dias**, aplicada com o sweep — `python tools/logread.py sweep --folder
<dir-logs> --max-mb <teto>` (M4.6: o teto de tamanho é o mecanismo; o
agendamento entra com o deploy de produção, M4.8 — até lá, rodada manual).

### 1.5 Não implementado (dados futuros — reavaliar ao implementar)

- **Áudio de quiosque / tour em áudio**: hoje inexistente. Se gravar voz de
  visitante, é dado pessoal sensível em potencial → consentimento e retenção
  próprios **antes** do lançamento da feature.
- **Analytics de visitação**: inexistente. Se um cliente pedir, preferir
  métricas agregadas sem cookies (ex.: contagem server-side por path).
- **Loja (módulo `store`)**: produtos são exibidos, não há checkout. Com
  checkout, entram dados de pagamento → reavaliação completa (PCI, gateway).

## 2. Bases legais (resumo para o jurídico)

| Tratamento | Base provável (LGPD art. 7º) |
|---|---|
| Pergunta ao assistente | Execução do serviço solicitado pelo titular (a pergunta) + legítimo interesse com minimização |
| `ip_hash` + telemetria | Legítimo interesse (segurança, anti-abuso, custo) — pseudonimizado, retido ≤ 90 dias |
| Logs operacionais | Legítimo interesse (operação e segurança) |
| Rótulo de e-mail do admin | Execução de contrato (o museu é o controlador dos dados da sua equipe) |

## 3. Direitos dos titulares (resposta operacional)

Como **não há contas nem dados identificáveis de visitante**, os pedidos de
acesso/eliminação se resolvem assim:

1. Visitante: declarar que não mantemos dados pessoais identificáveis (o
   `ip_hash` não é reversível sem uma lista de IPs, que não mantemos).
2. Curador (via museu empregador): editar/remover o rótulo de e-mail é
   trivial; o histórico de `api_write` pertence ao acervo (interesse do museu).
3. Canal de contato do encarregado (DPO) fica na página de privacidade do
   cliente — o modelo tem o campo.

## 4. Suboperadores

| Operador | Função | Dados |
|---|---|---|
| DeepSeek | LLM do assistente | texto da pergunta (sem identificadores) |
| Cloudflare | R2 (mídia) + Turnstile | requisições de mídia; token de verificação |
| GitHub | Pages (site), Actions (CI), ghcr (imagem) | logs de acesso às páginas |

## 5. Checklist de conformidade por cliente (onboarding)

- [ ] Adaptar e publicar a página de privacidade (`docs/privacidade-modelo.md`)
      com nome do museu, CNPJ, contato do encarregado e link no rodapé do site.
- [ ] Preencher `licenca` + `fonte` em **todo** card com mídia pública
      (contrato 1.2.0; o site renderiza os dois na visualização da peça).
      Verificar que o cliente tem direito de exibir cada asset.
- [ ] Configurar a retenção de logs (sweep agendado, teto de MB) no deploy de
      produção — alvo padrão: 90 dias.
- [ ] Confirmar DPAs/termos dos suboperadores (DeepSeek, Cloudflare, GitHub).
- [ ] Se o cliente ativar módulos novos (loja com checkout, áudio de
      quiosque, analytics), reabrir este inventário **antes** do go-live.
- [ ] Registrar quem é o controlador (o museu) e quem é o operador (a
      plataforma) no contrato de serviço — ver HANDOFF §Comercial.

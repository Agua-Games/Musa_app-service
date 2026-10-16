# Runbook operacional — MUSA app-service

> Semeado na **M4.3** (2026-10-16) com a rotação de credenciais; a M4.4
> expande com onboarding de cliente, incidentes, rollback e backup/restore.
> Cada procedimento diz **quando**, **como** e **o que quebra**.

## Rotação de credenciais

Regra geral: credencial boa é credencial com data de troca marcada. Suspeita
de vazamento → rotaciona **na hora**, investiga depois.

| Credencial | Onde vive | Quando rotacionar |
|---|---|---|
| `MUSA_ADMIN_TOKEN` (por tenant) | env do processo `serve` (App Service, M4.8) | trimestral; suspeita de vazamento; saída de alguém da equipe do museu |
| `DEEPSEEK_API_KEY` | env do `serve` (nunca no repo, nunca no browser) | semestral; suspeita; fatura anômala (ver telemetria `assistant_ask`) |
| `MUSA_TURNSTILE_SECRET` | env do `serve` | anual; suspeita |
| R2 access key/secret (`MUSA_R2_*`) | env local/CI de quem roda `upload` | anual; suspeita — **PENDENTE: o secret exposto no chat em 2026-10-07 deve ser rotacionado (dono)** |
| Chave privada Ed25519 da plataforma | fora de qualquer repo (`H:\Musa_app-service\secrets\`) | só comprometimento — operação rara, ver `docs/entitlements.md` |
| `GHCR_PULL_TOKEN` (PAT `read:packages`) | secret de cada repo cliente | anual; suspeita |

### `MUSA_ADMIN_TOKEN` (um por museu)

1. Gere o novo: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Atualize a variável de ambiente do serviço e reinicie o processo.
3. Entregue o novo token ao curador por canal seguro (nunca e-mail/chat aberto).

**O que quebra:** todas as sessões de admin caem no restart (o token antigo
morre junto) — avise o curador antes. O site público não é afetado.

### `DEEPSEEK_API_KEY`

1. Console DeepSeek → criar nova chave.
2. Atualize o env do `serve` e reinicie.
3. Revogue a chave antiga no console.

**O que quebra:** entre o restart e a revogação, nada — as duas valem. Se a
chave morrer sem reposição, o assistente entra em `not_configured` (503
educado) e o circuit breaker segura o resto — o site nunca quebra por causa
do assistente.

### R2 (`MUSA_R2_ACCESS_KEY_ID` / `MUSA_R2_SECRET_ACCESS_KEY`)

1. Cloudflare → R2 → Manage R2 API Tokens → criar token novo com o **mesmo
   escopo mínimo** (Object Read & Write, somente o bucket do museu).
2. Atualize o env onde o `upload` roda.
3. Delete o token antigo no painel.

**O que quebra:** nada enquanto os dois coexistirem. Sem escopo mínimo o
princípio de menor privilégio morre — nunca token "Entire Account".

### Chave privada Ed25519 da plataforma

Coberta em `docs/entitlements.md` §Operação: novo par → pública entra na
próxima release da imagem → **re-assinar todos os clientes**. Manual e rara
por desenho; o backup fora do repo é o que transforma "perda" em "rotação".

---

## A fazer na M4.4 (placeholders)

- **Onboarding de cliente novo** (repo → entitlements assinados → R2 → Pages/Container Apps).
- **Incidentes**: assistente fora, provider de LLM fora, R2 fora, deploy quebrado.
- **Rollback de versão** do app (pin `musa` no config do cliente).
- **Backup local + restore ensaiado e cronometrado** (DR drill).

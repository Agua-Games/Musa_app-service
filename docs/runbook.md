# Runbook operacional — MUSA app-service

> Semeado na **M4.3** (2026-10-16) com a rotação de credenciais; expandido
> na **M4.4** com onboarding de cliente, incidentes, rollback, alertas e
> backup/restore.
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

## Onboarding de cliente novo

Ponta a ponta, do zero ao site no ar. Decisões de arquitetura: ADR 0003
(repo por cliente = conteúdo + config + CI, sem código MUSA) e
`docs/entitlements.md` (tier/módulos assinados pela plataforma).

1. **Criar o repo do cliente** a partir do template (`musa-client-template`),
   **sem** fork nem parentesco de histórico — "Use this template" no GitHub.
2. **`museum.config.json`**: preencher `museum.id`, nome, idioma, e o pin
   `musa` na **tag** da imagem desejada (nunca `latest` em produção).
3. **Assinar os entitlements** (passo da plataforma, não do cliente):

   ```bash
   python tools/sign_entitlements.py sign --repo <repo-cliente> \
       --key H:\Musa_app-service\secrets\musa-entitlements-ed25519.key
   ```

   Defina tier (`bronze|silver|gold`) e módulos antes de assinar — a
   assinatura cobre exatamente o que estiver no arquivo.
4. **Bucket R2** (passo do dono, painel Cloudflare): criar
   `musa-assets-<cliente>`, gerar API token com **Object Read & Write
   somente naquele bucket**, sem filtro de IP. Ativar o domínio público
   `r2.dev` do bucket. **Atenção:** a conta Cloudflare atual é pessoal e
   temporária — ver `docs/M4_plano.md` antes de mover volume grande.
5. **Secret `GHCR_PULL_TOKEN`** no repo do cliente (passo do dono): PAT com
   `read:packages` → Settings → Secrets and variables → Actions.
6. **Pages → "GitHub Actions"** no repo do cliente (passo do dono).
7. **Primeiro push**: o CI do cliente baixa a imagem `ghcr.io/<org>/musa:<tag>`,
   roda o gate (contrato + tier + drafts) e publica. Se o gate falhar, o
   deploy não acontece — é o comportamento correto, leia o build-report.
8. **Vincular o pacote ghcr.io ao repositório** (passo do dono, após o
   primeiro push da imagem): página do pacote → Package settings →
   "Connect repository" — senão a imagem não herda a visibilidade do repo.
9. **Entregar ao curador**: URL do site, URL do `/admin`, e o
   `MUSA_ADMIN_TOKEN` gerado para aquele tenant (ver §Rotação).
10. **Verificação de aceite**: `python -m musa_build audit --repo <repo>` —
    deve sair sem erros; abrir o site e confirmar as coleções públicas.

**O que quebra:** pular o passo 3 → o gate rejeita o build (entitlements
inválidos). Pular o 5 → o CI não baixa a imagem (403 do ghcr). Pular o 8 →
imagem invisível para o CI de outras contas.

---

## Incidentes

### Assistente responde 503 / "temporariamente indisponível"

1. Confira o outcome no log JSONL do serve (`assistant_ask`): `not_configured`
   (sem `DEEPSEEK_API_KEY` no env), `provider_error` (DeepSeek fora/lento),
   `quota_exceeded` (cota de uso atingida) ou `breaker_open`.
2. `not_configured` → configure a variável e reinicie o processo.
3. `provider_error` repetido → verifique o status da DeepSeek; o circuit
   breaker abre sozinho e segura o resto do site — **não** reinicie em loop.
4. `quota_exceeded` → a cota diária de tokens estourou (proteção de custo);
   aumente o limite no env ou aguarde o reset de meia-noite UTC.

**O que quebra:** nada além do assistente. O site, o catálogo e o admin
continuam — degradação proposital.

### R2 / assets fora do ar

1. Sintoma: imagens quebradas no site, uploads falhando no admin.
2. Verifique o status da Cloudflare e se o token R2 não expirou/foi revogado.
3. O site segue servindo textos e catálogo; só mídia degrada.

### Deploy quebrado no GitHub Actions do cliente

1. Actions → workflow com falha → leia o step: `pull` (403 →
   `GHCR_PULL_TOKEN`), `gate` (build-report no log diz exatamente qual card
   ou regra reprovou), `deploy` (Pages).
2. Gate reprovando card → corrija o card no repo e faça push de novo; **não**
   tente contornar o gate, ele é a garantia contratual.

### Coleção errada / card errado no site público

1. Leia o `build-report` do último deploy (artefato do Actions).
2. O gate bloqueia conteúdo inválido; se algo válido porém errado subiu,
   corrija o registro (admin ou repo) e republique — a publicação fim-a-fim
   mediana é ~36 s (SLO, `docs/M3_slos.md`).

---

## Rollback de versão do app

As tags de imagem são **imutáveis**: `<tag>` aponta sempre para o mesmo
build. Rollback = re-pin, não rebuild.

1. No repo do cliente, edite `museum.config.json`: campo `musa` de volta à
   tag anterior (ex.: `0.4.0` → `0.3.2`).
2. Push. O CI reconstrói o site com a versão anterior e o gate valida.
3. Se a versão anterior não existir mais no ghcr (retenção), escolha a tag
   disponível mais próxima (`docker`/`crane` ou a página do pacote listam).

**O que quebra:** features novas usadas pelos cards do cliente podem não
existir na versão antiga — o gate reprova o build nesse caso e o deploy não
acontece (o site anterior continua no ar).

---

## Alertas

Cinco regras por dia UTC sobre o log JSONL do serve, implementadas e
testadas em `builder/musa_build/alerts.py` (limiares são pontos de partida,
não SLO contratual — ajuste por tenant):

| Regra | Dispara quando | Ação sugerida |
|---|---|---|
| custo-assistente | soma de `cost_usd_estimate` do dia > teto (padrão US$ 0,50) | revisar cota de tokens; checar abuso no log |
| cota-estourada | qualquer `quota_exceeded` no dia | usuário real bloqueado → aumentar cota ou investigar bot |
| cards-rejeitados | 422 em POST `/items` ou `/collections` > teto (padrão 10/dia) | treinar o curador ou revisar a validação |
| egress-assets | GET `/assets/` 200 > faixa (padrão 50.000/dia; 404 não conta) | verificar hot-linking/crawl; CORS/cache |
| qualquer-5xx | qualquer resposta 5xx | incidente — ver §Incidentes |

**Como rodar:**

```bash
python tools/check_alerts.py <serve-log.jsonl> \
    [--custo-dia 0.50] [--rejeicoes-dia 10] [--assets-dia 50000]
# exit 0 = limpo · exit 1 = alerta (imprime ALERTA: ...) · exit 2 = log ausente
```

**Canais de notificação:**

- **Build quebrado / card rejeitado no gate** → CI do repo cliente falha
  vermelho + e-mail nativo do GitHub Actions (já funciona, zero custo).
- **Runtime** → agendar `tools/check_alerts.py` (Task Scheduler/cron; na
  M4.8 vira alerta do Azure Monitor) sobre o log do serve; exit 1 dispara o
  canal escolhido (e-mail/webhook).
- **R2/Cloudflare** → notifications do painel para o bucket (dono).

---

## Backup e restore (overlay `.musa/`)

O repo do cliente é a semente (RPO = GitHub). As edições do dia a dia feitas
pelo admin vivem **só** no overlay SQLite (`<repo>/.musa/state.db`) — sem
backup, o RPO delas é "até o próximo commit". Referência de desempenho: DR
drill completo cronometrado em `docs/dr-drill-ata.md` (RTO medido 4,5 s vs
meta 5 min).

**Backup** (seguro com o serve vivo — usa a backup API do SQLite):

```bash
python -m musa_build backup --repo <repo-cliente> --out <dir-backups>
# cria musa-backup-<museum>-<timestamp>/ com state.db + manifest.json (sha256)
```

**Restore** (recusa museum errado ou cópia corrompida **antes** de escrever;
preserva o overlay atual em `state.before-restore-<ts>`; prova o boot no
final — restore que não boota é reportado como falha):

```bash
python -m musa_build restore --repo <repo-cliente> \
    --from <dir-backups>/musa-backup-<museum>-<timestamp>
# exit 0 ok · exit 2 precondição falhou (nada foi escrito)
```

**Retenção sugerida:** diário local (7 cópias) + semanal fora da máquina
(4 cópias). Restore ensaiado **mensalmente** — backup não testado é
decorativo. Para ensaiar o desastre inteiro (apaga repo + overlay, re-clona,
restaura, boota, mede): `python tools/dr_drill.py --repo <repo-cliente>`.

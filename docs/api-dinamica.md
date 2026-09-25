# API dinâmica do acervo (M1.4) — `musa-build serve`

O backend mínimo da ADR 0008 roda na **mesma imagem** do builder, como um segundo
comando. Um runtime só (Python), um pipeline de artefato só.

## Subir a API de um museu

```bash
# na imagem / pacote musa-app:
MUSA_ADMIN_TOKEN=<token-do-tenant> \
  python -m musa_build serve --repo /caminho/do/repo-do-cliente --port 8000
# ou com a imagem de contêiner:
docker run --rm -p 8000:8000 -v ${PWD}:/work -e MUSA_ADMIN_TOKEN=<token> \
  ghcr.io/agua-games/musa-app:<versão> serve --repo /work --host 0.0.0.0 --port 8000
```

- **`MUSA_ADMIN_TOKEN`** — bearer do tenant. Sem ela a instância sobe **read-only**
  (`/health` responde `"writes": "disabled"` e escritas retornam 503). Nesta fase o
  login do admin usa o token no campo de senha; contas com papéis vêm com o backend
  de escala (ADR 0008).
- **Estado** — o repo do cliente é o *seed* (versionado, auditável). As edições do
  admin vivem num overlay SQLite em `<repo>/.musa/state.db` (já está no `.gitignore`
  dos clientes — o admin nunca suja o git do cliente). Apagar `.musa/` volta o museu
  ao estado do repo.
- **Gating idêntico ao build** — draft/tier acima = 404 para o público, e os assets
  desses registros não são servidos. Com o token, o admin enxerga os próprios
  rascunhos (`?include_drafts=1`); o portão de tier nunca relaxa.

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| GET | `/health` | liveness; informa se writes estão habilitados |
| GET | `/schema` | o contrato do card, verbatim |
| GET | `/collections` | coleções públicas (gated) |
| GET | `/collections/{id}/items[?include_drafts=1]` | itens; drafts só com token |
| GET | `/items/{asset_id}` | registro completo; draft só com token |
| GET | `/search?q=...` | índice de termos sobre os itens públicos |
| GET | `/assets/content/...` | assets de registros incluídos, somente |
| POST | `/auth/login` | `{email, password: <token>}` → `{token, user}` |
| POST | `/collections` | `{id, title, description?, tier?}` — 409 se já existe |
| POST | `/items` | patch (`{asset_id, ...campos}`) ou criação (card completo; nasce `draft`) |

Todas as respostas de coleção usam o envelope `{ data, meta }` da API estática
(docs/api-estatica.md) — o frontend troca de modo mudando só o `baseUrl`.

## Apontar um site de cliente para a API dinâmica

O build emite `data/runtime.js` em modo estático. Para ligar o modo dinâmico
(ex.: teste local do admin), sirva o site buildado e sobrescreva o runtime:

```js
window.MUSA_RUNTIME = { mode: "live", baseUrl: "http://127.0.0.1:8000", static: false };
```

O CORS da API está aberto (`*`) — auth é por bearer, sem cookies; restringir ao
domínio do tenant é refinamento de deploy. Com `static: false`, o admin persiste
de verdade: login → criar coleção → criar item (nasce rascunho) → publicar.

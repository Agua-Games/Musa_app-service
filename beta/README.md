# beta/ — cliente virtual (M3)

Personas sintéticas que operam um museu cliente pelo caminho real do curador:
HTTP contra o `musa-build serve` (ADR 0014). Roda sobre uma **cópia descartável**
do repo do cliente — nada é commitado, deployado ou enviado ao R2
(restrições 2 e 4 do `docs/M3_plano.md`).

## Rodar localmente (a partir da raiz da plataforma)

```bash
python -m beta.run_beta --repo H:\Musa_app-service\DemoMuseum --seed 42
python -m beta.run_beta --repo <repo> --routines diaria --no-build-check
```

- `--seed` — mesma seed + mesmo estado inicial ⇒ mesma sequência de ações.
- `--routines` — `diaria`, `semanal`, `pontual` ou `all` (padrão).
- `--out` — onde gravar `beta-log-*.jsonl` e `beta-report-*.json`
  (padrão `beta/out/`, gitignored).
- `--no-build-check` — pula o invariante lento de build verde por sessão.

Exit code: `0` tudo verde, `1` houve reprovação, `2` infra (serve não subiu).

## Estrutura

| Arquivo | Papel |
|---|---|
| `client.py` | sessão HTTP do curador (login, CRUD via API pública) |
| `personas.py` | `owner@demo` / `team@demo`, rotinas com seed; lacunas de API viram achados (`achado-gap`) |
| `invariants.py` | asserções após cada ação (sem draft público, portão de tier, contrato válido, build verde) |
| `run_beta.py` | orquestrador: clone descartável → serve → rotinas → JSONL + relatório |
| `tests/` | determinismo de seed, rodada verde no fixture, sanidade dos invariantes (cada um é forçado a falhar uma vez) |

## Testes

```bash
python -m unittest discover -s beta/tests -t .
```

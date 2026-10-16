# Comandos de console do dev MUSA

Os comandos do dia a dia, na ordem em que costumam ser usados. Todos assumem a
raiz da plataforma (`H:\Musa_app-service\alpha`) como ponto de partida, salvo
indicação. O DemoMuseum fica no diretório irmão `H:\Musa_app-service\DemoMuseum`.

---

## Testes (rodar sempre antes de push)

```bash
# Builder + contrato + serve + upload (105 testes, ~2 s) — roda com cwd=builder
cd builder && python -m unittest discover -s tests

# Servidor MCP (13 testes, instantâneo)
cd mcp_server && python -m unittest discover -s tests

# Cliente virtual: personas + uso indevido (10 testes, ~25 s — sobem um serve real)
# roda da RAIZ da plataforma, com -t . (os testes importam beta.*)
python -m unittest discover -s beta/tests -t .

# Pipeline de catalogação (3 testes estruturais no Python gerenciado; os 3
# semânticos exigem o venv da pipeline)
python pipeline/test_structure.py
pipeline/.venv/Scripts/python pipeline/test_semantic.py
```

## Build e validação de um museu cliente

```bash
# Build completo: valida cards contra o contrato, aplica o portão
# (draft/tier) e emite o site estático em <out>. Falha = site anterior fica no ar.
cd builder && python -m musa_build build --repo "H:\Musa_app-service\DemoMuseum" \
  --frontend "H:\Musa_app-service\alpha\source" --out %TEMP%\musa-site

# Só valida e reporta (sem emitir o site) — mais rápido para depurar cards
cd builder && python -m musa_build validate --repo "H:\Musa_app-service\DemoMuseum" \
  --frontend "H:\Musa_app-service\alpha\source"
```

## Servir a API dinâmica localmente (modo admin)

```bash
# Sobe a API do acervo na porta 8000. SEM MUSA_ADMIN_TOKEN a instância é
# read-only (writes = 503). O overlay de escritas vai para <repo>/.musa/
# (gitignored) — apagar .musa/ volta o museu ao estado do repo.
set MUSA_ADMIN_TOKEN=token-local-de-teste
cd builder && python -m musa_build serve --repo "H:\Musa_app-service\DemoMuseum" --port 8000

# Overlay num diretório descartável (testes que não devem tocar nem o .musa/):
cd builder && python -m musa_build serve --repo <repo> --data-dir %TEMP%\musa-overlay --port 8000
```

## Assistente (M4.2) — POST /assistant/ask
```bash
# Modo dev SEM gastar token: provedor fake determinístico (respostas simuladas,
# pipeline completo exercitado). É o modo que o beta/CI usam, sempre.
set MUSA_LLM_FAKE=1

# Modo real: provedor DeepSeek (a chave NUNCA vai para o repo do cliente nem
# para o browser — só no processo do serve).
set DEEPSEEK_API_KEY=sk-...
set MUSA_DEEPSEEK_MODEL=deepseek-chat        :: opcional; padrão deepseek-chat

# Knobs anti-abuso (todos opcionais, com padrões sensatos):
set MUSA_ASSISTANT_RPM=10                    :: rate limit por IP (req/min)
set MUSA_ASSISTANT_DAILY_TOKENS=200000       :: cota de tokens por museu/dia UTC
set MUSA_TURNSTILE_SECRET=...                :: só com isto o Turnstile é exigido

# Telemetria: todo ask loga o evento assistant_ask (outcome, tokens,
# cost_usd_estimate, hash do IP — nunca o IP cru).
```

## Segurança auditável (M4.3)

```bash
# Auditoria de gating: PROVA, sonda a sonda, que nenhum rascunho e nada
# acima do tier vaza para o público (JSON, arquivos, busca) — com controle
# positivo (admin vê rascunhos; tier nunca relaxa). Gera relatório em PT
# claro, anexável a contrato. Exit 1 se houver qualquer vazamento.
cd builder && python -m musa_build audit --repo "H:\Musa_app-service\DemoMuseum" --out ..\docs\auditoria-gating-demo-museum.md

# Rate limits de escrita/login (por IP; 0 desliga — uso do harness de carga):
set MUSA_WRITE_RPM=60     :: padrão 60/min — POST /items e /collections
set MUSA_LOGIN_RPM=5      :: padrão 5/min — POST /auth/login (anti-brute-force)

# Entitlements assinados obrigatórios (a imagem publicada JÁ exporta =1;
# local só se você quiser simular o ambiente de release):
set MUSA_REQUIRE_SIGNED_ENTITLEMENTS=1

# Rotação de credenciais (tokens, chaves R2, DeepSeek, Ed25519): docs/runbook.md
```

## Upload de assets para o R2 (Cloudflare)

```bash
# Sobe os assets locais dos cards e reescreve os cards para as URLs públicas.
# Credenciais SÓ por variável de ambiente — nunca no repo (MUSA_R2_* ou AWS_*):
set MUSA_R2_ACCESS_KEY_ID=...
set MUSA_R2_SECRET_ACCESS_KEY=...
cd builder && python -m musa_build upload --repo "H:\Musa_app-service\DemoMuseum"
```

## API reference (gerada — nunca editada à mão)

```bash
# Regenera docs/api-reference.md a partir das rotas do serve + contrato do
# card. Endpoint novo sem anotação em ANNOTATIONS (musa_build/api_reference.py)
# = erro; doc velho no disco = suíte do builder falha (test_api_reference.py).
cd builder && python -m musa_build api-reference

# Só confere se o doc está em sincronia (exit 1 = stale)
cd builder && python -m musa_build api-reference --check
```

## Cliente virtual (M3) — personas + gerador de uso indevido

```bash
# Rodada completa contra clone descartável do DemoMuseum: personas (rotinas
# diária/semanal/pontual) + 10 cenários hostis + invariantes. Custo zero:
# nada toca o R2, o repo real ou o Pages. Exit 0 = verde; 1 = reprovação.
python -m beta.run_beta --repo "H:\Musa_app-service\DemoMuseum" --seed 42 --suite all

# Só personas / só o gerador de uso indevido
python -m beta.run_beta --repo <repo> --suite personas --no-build-check
python -m beta.run_beta --repo <repo> --suite misuse

# Flags: --seed N (mesma seed = mesma sequência) · --routines diaria|semanal|pontual|all
#        --no-build-check (pula o build-verde, mais rápido) · --out <dir> dos logs
# Saída: beta/out/beta-log-<run>.jsonl (1 evento/ação) + beta-report-<run>.json
```

## Pipeline de catalogação (M2) — venv próprio em pipeline/.venv

```bash
# Chave do LLM fica no cofre local (nunca no repo):
#   source "/c/Users/Athos/AppData/Roaming/reasonix/.env"   (exporta DEEPSEEK_API_KEY)

pipeline/.venv/Scripts/python pipeline/run_ocr.py                # OCR em lote (resumível; --limit/--offset para fatias)
pipeline/.venv/Scripts/python pipeline/structure_agent.py --provider deepseek --batch-size 20
#   --provider mock = offline, sem custo · --batch-size N = N fichas por request (~30% mais barato)
python pipeline/confidence_report.py                             # cruza OCR+card+gabarito → X% sem revisão
pipeline/.venv/Scripts/python pipeline/build_vector_index.py --repo "H:\Musa_app-service\DemoMuseum"
python pipeline/import_to_museum.py --repo <repo> --collection acervo-importado
# Detalhes e corpus: pipeline/README.md
```

## Carga (M3.5) — N museus × M itens

```bash
# Mede build/payload/startup/latências em 500/2.000/5.000/10.000 cards +
# memória marginal por instância de serve (1/2/4/8 museus), e REESCREVE
# docs/M3_carga.md. 100% local: corpus só de metadados, zero rede, zero R2.
# Resumível: escalas já medidas ficam em beta/out/load-state.json (pule com --reset).
python -m beta.load
python -m beta.load --scales 500,2000      # parcial
python -m beta.load --scales "" --skip-museums   # só re-renderiza o doc
```

## GitHub / CI do cliente (gh CLI)

```bash
# O gh desta máquina:
GH="$LOCALAPPDATA/Programs/GitHubCLI/bin/gh.exe"

# Disparar o build+deploy do DemoMuseum (dry-run=true só valida, não publica)
"$GH" workflow run deploy.yml -R Agua-Games/DemoMuseum -f dry-run=false

# Ver o último run e seguir o log
"$GH" run list -R Agua-Games/DemoMuseum --limit 3
"$GH" run watch -R Agua-Games/DemoMuseum --exit-status
```

## Imagem de contêiner (artefato de distribuição, ADR 0006)

```bash
# Build local da imagem (o CI faz o push para ghcr.io/agua-games/musa-app:<tag>)
docker build -t musa-app:dev .

# Rodar o serve de um repo cliente DENTRO da imagem publicada
docker run --rm -p 8000:8000 -v ${PWD}:/work -e MUSA_ADMIN_TOKEN=<token> \
  ghcr.io/agua-games/musa-app:<versão> serve --repo /work --host 0.0.0.0 --port 8000
```

## Git — convenções do estúdio

```bash
# Mensagens em inglês, imperativo minúsculo: tipo(escopo): descrição
#   feat(builder): ... · fix(serve): ... · docs: ... · test(beta): ...
git log --oneline -10      # ver o padrão antes de commitar
```

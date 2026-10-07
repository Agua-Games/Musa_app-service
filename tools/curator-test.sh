#!/usr/bin/env bash
# M1.4 curator test (exit criterion: a non-technical curator creates a
# collection and publishes an item, unaided, in < 15 minutes).
#
# Run from Git Bash:   bash tools/curator-test.sh
# It builds the DemoMuseum site, points it at a LOCAL dynamic API and starts
# both servers. Ctrl+C stops everything; the write state is a throwaway dir.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/scratch/curator-test"
SITE="$WORK/site"
DATA="$WORK/data"
TOKEN="curador-demo"
API_PORT=8000
SITE_PORT=8001

rm -rf "$WORK" 2>/dev/null || true
mkdir -p "$WORK" "$DATA"

echo "== building the DemoMuseum site (fresh) =="
(cd "$ROOT/builder" && python -m musa_build build --repo "$ROOT/../DemoMuseum" --frontend "$ROOT/source" --out "$SITE")

echo "== pointing the site at the local API (dynamic mode) =="
cat > "$SITE/data/runtime.js" << JS
window.MUSA_RUNTIME = { mode: "live", baseUrl: "http://127.0.0.1:$API_PORT", static: false };
JS

echo "== starting the collection API (writes enabled, throwaway state) =="
(cd "$ROOT/builder" && MUSA_ADMIN_TOKEN="$TOKEN" python -m musa_build serve \
  --repo "$ROOT/../DemoMuseum" --data-dir "$DATA" --port $API_PORT) &
API_PID=$!
(cd "$SITE" && python -m http.server $SITE_PORT > /dev/null 2>&1) &
SITE_PID=$!
trap 'kill $API_PID $SITE_PID 2>/dev/null || true' EXIT

sleep 3
cat << TXT

==============================================================
 TESTE DO CURADOR (M1.4) — comece a cronometrar agora
==============================================================
 1. Abra  http://127.0.0.1:$SITE_PORT
 2. Menu "Sign in": qualquer e-mail; senha = $TOKEN
 3. No painel "Venue admin":
    a. "+ Collection" — invente slug e título; Save
    b. Clique na coleção criada → "+ Item" — slug, título,
       autor, ano e uma URL de imagem qualquer; Save
       (o item nasce RASCUNHO — some do site, fica no painel)
    c. Selecione o item na lista → "Publish to website"
 4. Recarregue a página (ou abra anônima) e ache o item no site.

 Critério: tudo isso SEM AJUDA, em menos de 15 minutos.
 Ctrl+C nesta janela encerra os servidores (estado descartável).
==============================================================
TXT
wait

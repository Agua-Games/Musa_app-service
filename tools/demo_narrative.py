"""M4.7 — the 5-minute investor narrative, EXECUTED end to end (not narrated).

Beats (docs/M4_plano.md §M4.7 verification):

1. **bronze online** — the photo catalog is public; Gold features (assistant,
   store) answer 404: the module gate is real.
2. **acessar a conta** — the curator logs in with the tenant token.
3. **publicar uma peça** — created and published through the API, visible
   publicly in real time (no rebuild, no deploy).
4. **upgrade de tier** — the platform RE-SIGNS the entitlements (bronze ->
   gold + modules) with the real Ed25519 key — the genuine operation.
5. **o recurso Gold aparece** — after a reboot the store and the assistant
   answer 200, and a gold-tier piece is served.

The demo repo's config is restored at the end, so the narrative is
re-runnable. Exit 0 = every beat landed. The human-facing script (what to
say while each beat runs) is demos/ROTEIRO.md.

Usage (from the platform repo root):

    python tools/demo_narrative.py --repo H:\\Musa_app-service\\demos\\atelier-bronze \\
        --key H:\\Musa_app-service\\secrets\\musa-entitlements-ed25519.key
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PLATFORM_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLATFORM_ROOT))

from beta.harness import ServeHarness  # noqa: E402


class Beat:
    def __init__(self) -> None:
        self.t0 = time.perf_counter()

    def done(self, name: str, detail: str) -> None:
        print(f"  [{time.perf_counter() - self.t0:5.1f}s] {name}: {detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="the bronze demo repo")
    parser.add_argument("--key", required=True, help="platform Ed25519 private key file")
    args = parser.parse_args(argv)

    source_repo = Path(args.repo)
    if not (source_repo / "museum.config.json").is_file():
        print(f"FATAL: {source_repo} is not a client repo", file=sys.stderr)
        return 2

    print("M4.7 — narrativa de demonstração (executável)\n")
    tmp = Path(tempfile.mkdtemp(prefix="musa-narrative-"))
    harness = None
    failures = []
    try:
        # A disposable copy: the narrative upgrades tiers and publishes pieces;
        # the real demo repo must stay pristine for the next showing.
        repo = tmp / "repo"
        shutil.copytree(source_repo, repo)
        token = "narrative-demo-token"
        harness = ServeHarness(repo, tmp / "overlay", token=token, log_dir=tmp / "logs")

        beat = Beat()
        client = harness.boot()
        assert client is not None
        cols = client.collections()
        items_total = sum(client.collection_items(c["id"]).body["meta"]["count"]
                          for c in cols.body["data"])
        assistant_off = client.request("POST", "/assistant/ask", json={"question": "oi"}).status == 404
        store_off = client.request("GET", "/store/products").status == 404
        ok = cols.ok and items_total > 0 and assistant_off and store_off
        beat.done("1 · bronze no ar",
                  f"{len(cols.body['data'])} coleção(ões), {items_total} peças públicas; "
                  f"assistente 404: {assistant_off}; loja 404: {store_off}")
        if not ok:
            failures.append("bronze surface")

        beat = Beat()
        login = client.login("curador@atelier.example", token)
        beat.done("2 · acessar a conta", f"login do curador: HTTP {login.status}")
        if not login.ok:
            failures.append("login")

        beat = Beat()
        col_id = cols.body["data"][0]["id"]
        new_piece = {
            "asset_id": "estreia-da-temporada",
            "titulo": "Estreia da Temporada",
            "colecao": col_id,
            "autor": "Acervo do Atelier",
            "material": "Óleo sobre tela",
        }
        created = client.save_item(new_piece)
        client.save_item({"asset_id": "estreia-da-temporada", "website_status": "published"})
        visible = client.item("estreia-da-temporada")
        beat.done("3 · publicar uma peça",
                  f"criada e publicada; pública em tempo real: {visible.ok} (sem rebuild)")
        if not (created.ok and visible.ok):
            failures.append("publish")

        beat = Beat()
        config_path = repo / "museum.config.json"
        original_config = config_path.read_bytes()
        config = json.loads(original_config.decode("utf-8"))
        config["entitlements"]["tier"] = "gold"
        config["entitlements"]["modules"] = ["assistant", "store"]
        config["entitlements"].pop("signature", None)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(PLATFORM_ROOT / "tools" / "sign_entitlements.py"),
             "sign", "--repo", str(repo), "--key", args.key],
            capture_output=True, text=True)
        beat.done("4 · upgrade de tier",
                  "plataforma re-assina entitlements bronze → gold + [assistant, store] "
                  f"(operação real, Ed25519): exit {proc.returncode}")
        if proc.returncode != 0:
            failures.append("re-sign")

        beat = Beat()
        client = harness.reboot()
        assert client is not None
        client.login("curador@atelier.example", token)
        store = client.request("GET", "/store/products")
        assistant = client.request("POST", "/assistant/ask",
                                   json={"question": "quantas peças tem o acervo?"})
        gold_piece = client.save_item({
            "asset_id": "peca-gold-exclusiva", "titulo": "Peça Gold Exclusiva",
            "colecao": col_id, "autor": "Acervo do Atelier", "tier": "gold"})
        client.save_item({"asset_id": "peca-gold-exclusiva", "website_status": "published"})
        gold_visible = client.item("peca-gold-exclusiva")
        ok = store.ok and assistant.status == 200 and gold_piece.ok and gold_visible.ok
        beat.done("5 · o recurso Gold aparece",
                  f"loja HTTP {store.status}; assistente responde: {assistant.status == 200}; "
                  f"peça tier gold servida: {gold_visible.ok}")
        if not ok:
            failures.append("gold features")

        # Leave the disposable copy as it was found: the narrative is re-runnable.
        config_path.write_bytes(original_config)
    finally:
        if harness is not None:
            harness.stop()
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if failures:
        print(f"NARRATIVA REPROVADA — beats com falha: {failures}")
        return 1
    print("NARRATIVA APROVADA — os 5 beats executaram de ponta a ponta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

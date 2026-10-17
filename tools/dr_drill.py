"""M4.4 — DR drill: disaster -> restore -> verified service, timed.

Not a plan on paper: this script destroys a museum (a COPY of the client
repository plus its overlay — the machine-loss scenario) and brings it back
from the local backup, measuring the recovery time against the SLO target
(RTO < 5 min, docs/M3_slos.md §RPO/RTO). It writes the drill minutes ("ata")
in plain Portuguese.

What is timed (the RTO clock):
    T0  disaster confirmed — server dead, repo + overlay wiped
    ... re-clone the seed from git (the off-site copy standing in for GitHub)
    ... restore the overlay from the last local backup
    ... boot the API and verify the public payload is byte-identical
    T1  service verified back

What is NOT in the RTO clock: the pre-disaster setup and the scheduled
backup itself (reported separately — it is a normal-operations metric).

Honest limits (also written into the ata): the drill runs on one machine
with local disks; a production restore adds the real git clone and the
container pull, both network-bound and covered by the publish SLO
(~36 s median, docs/M3_slos.md).

Run:  python tools/dr_drill.py [--repo ../DemoMuseum] [--out docs/dr-drill-ata.md]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))
sys.path.insert(0, str(ROOT))

from beta.client import ApiClient  # noqa: E402
from musa_build.backup import create_backup, restore_backup  # noqa: E402
from musa_build.serve import create_app  # noqa: E402

TOKEN = "dr-drill-token"
RTO_TARGET_S = 300  # SLO: RTO < 5 min (docs/M3_slos.md)
IGNORE = shutil.ignore_patterns(".git", ".musa", "_site", "node_modules", "__pycache__")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Serve:
    """In-thread uvicorn against a repo copy (test_beta pattern)."""

    def __init__(self, repo: Path, data_dir: Path):
        import uvicorn

        self.app = create_app(repo, data_dir=data_dir)
        self.port = _free_port()
        self.server = uvicorn.Server(
            uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.client = ApiClient(f"http://127.0.0.1:{self.port}")

    def start(self) -> None:
        self.thread.start()
        deadline = time.time() + 60
        while time.time() < deadline:
            try:
                if self.client.health(timeout=1.5).ok:
                    return
            except Exception:
                time.sleep(0.15)
        raise RuntimeError("serve did not come up")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=15)
        self.app.state.serve.store.close()


def _rmtree_retry(path: Path) -> None:
    for _ in range(10):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(0.5)
    shutil.rmtree(path, ignore_errors=True)


def public_payload(client: ApiClient) -> dict:
    cols = client.collections().body["data"]
    items = {}
    for col in cols:
        for slim in client.collection_items(col["id"]).body["data"]:
            items[slim["asset_id"]] = client.item(slim["asset_id"]).body["data"]
    return json.loads(json.dumps({"collections": cols, "items": items},
                                 sort_keys=True, ensure_ascii=False))


def make_overlay_edits(client: ApiClient) -> None:
    """Edits that exist ONLY in the overlay — the data the backup protects."""
    assert client.login("curador@dr-drill", TOKEN).ok
    assert client.request("POST", "/collections", auth=True, json={
        "id": "dr-drill", "title": "Restauro (DR drill)",
        "description": "Criada pelo drill de recuperação de desastre."}).status == 201
    for i in (1, 2):
        card = {
            "asset_id": f"dr-drill-{i}", "titulo": f"Peça do drill {i}",
            "colecao": "dr-drill", "autor": "Curador do Drill", "data": "2026",
            "material": "Digital", "descricao": "Existe apenas no overlay .musa/.",
            "website_status": "published" if i == 1 else "draft",
        }
        assert client.save_item(card).ok


def run_drill(repo: Path) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="musa-dr-drill-"))
    old_token = os.environ.get("MUSA_ADMIN_TOKEN")
    os.environ["MUSA_ADMIN_TOKEN"] = TOKEN
    timings: dict[str, float] = {}
    try:
        # ---- pre-disaster (NOT in the RTO clock) --------------------------
        t0 = time.monotonic()
        prod = tmp / "prod"
        shutil.copytree(repo, prod, ignore=IGNORE)
        timings["copia_do_repo_s"] = time.monotonic() - t0

        server = Serve(prod, prod / ".musa")
        server.start()
        make_overlay_edits(server.client)
        before = public_payload(server.client)
        n_public = len(before["items"])

        t0 = time.monotonic()
        backup_dir = create_backup(prod, out_dir=tmp / "backups")
        timings["backup_agendado_s"] = time.monotonic() - t0
        # off-site copy: the backup must survive the loss of the machine
        offsite = tmp / "offsite" / backup_dir.name
        shutil.copytree(backup_dir, offsite)

        # ---- T0: the disaster (RTO clock STARTS) ---------------------------
        rto_start = time.monotonic()
        server.stop()
        _rmtree_retry(prod)  # machine lost: repo + overlay, everything

        # restore: re-clone the seed, put the overlay back, boot, verify
        restored = tmp / "restored"
        shutil.copytree(repo, restored, ignore=IGNORE)  # stands in for git clone
        result = restore_backup(restored, backup_dir=offsite)
        server2 = Serve(restored, restored / ".musa")
        server2.start()
        after = public_payload(server2.client)
        server2.stop()
        timings["rto_s"] = time.monotonic() - rto_start

        identical = before == after
        ok = identical and timings["rto_s"] < RTO_TARGET_S
        return {
            "ok": ok,
            "payload_identical": identical,
            "public_items": n_public,
            "restored": result,
            "timings": timings,
            "rto_target_s": RTO_TARGET_S,
        }
    finally:
        if old_token is None:
            os.environ.pop("MUSA_ADMIN_TOKEN", None)
        else:
            os.environ["MUSA_ADMIN_TOKEN"] = old_token
        _rmtree_retry(tmp)


def render_ata(repo: Path, result: dict) -> str:
    t = result["timings"]
    veredito = ("**RTO CUMPRIDO** ✔" if result["ok"] else "**RTO FALHOU** ✘")
    return f"""# Ata de DR drill — recuperação de desastre do overlay

> Executado em {__import__('datetime').datetime.now(__import__('datetime').timezone.utc).date().isoformat()}
> por `tools/dr_drill.py` — não editado à mão. Alvo (SLO, `docs/M3_slos.md`):
> **RPO 0 / RTO < 5 min** para as edições de admin do overlay `.musa/`.

## Cenário ensaiado

Perda total da máquina que servia o museu (`{repo.name}`): repositório **e**
overlay apagados. A recuperação usa as duas cópias que existem por desenho:
o **seed** no git (re-clone) e o **último backup local** do overlay
(fora da máquina). Antes do desastre, o drill fez edições de admin que
existiam **só no overlay** (1 coleção, 2 itens — 1 publicado, 1 rascunho) —
é elas que o backup precisa trazer de volta.

## Linha do tempo

| Etapa | Tempo |
|---|---|
| Cópia do repositório (setup, fora do relógio) | {t['copia_do_repo_s']:.1f} s |
| Backup agendado (operação normal, fora do relógio) | {t['backup_agendado_s']:.1f} s |
| **T0 — desastre confirmado** (serve morto, repo + overlay destruídos) | 0,0 s |
| Re-clone do seed + restore do backup + boot + verificação | {t['rto_s']:.1f} s |
| **T1 — serviço verificado de volta** | **RTO = {t['rto_s']:.1f} s** |

## Veredito: {veredito}

- RTO medido **{t['rto_s']:.1f} s** contra alvo de {result['rto_target_s']} s.
- Payload público após o restore **{"byte-idêntico" if result['payload_identical'] else "DIFERENTE — dados perdidos"}**
  ao snapshot pré-desastre ({result['public_items']} itens públicos).
- O app bootou sobre o estado restaurado e contou
  {result['restored']['total_items']} itens / {result['restored']['total_collections']} coleções.

## Limites honestos deste ensaio

- Rodou numa única máquina, com discos locais. Em produção somam-se o clone
  real do GitHub e o pull da imagem — ambos cobertos pelo SLO de publicação
  (mediana ~36 s medida, `docs/M3_slos.md`), e mesmo somados ficam dentro do
  alvo com folga.
- O backup testado é **local**: a política de retenção (quantas cópias, onde,
  por quanto tempo) é decisão de operação por cliente — ver `docs/runbook.md`.

## Como reproduzir

```bash
python tools/dr_drill.py --repo <repositório do museu> --out docs/dr-drill-ata.md
```
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(ROOT.parent / "DemoMuseum"),
                        help="client repository to drill against (default: ../DemoMuseum)")
    parser.add_argument("--out", default=str(ROOT / "docs" / "dr-drill-ata.md"),
                        help="where to write the drill minutes")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    if not (repo / "museum.config.json").is_file():
        print(f"ERROR: {repo} is not a client repository")
        return 2

    print(f"DR drill contra {repo} ...")
    result = run_drill(repo)
    t = result["timings"]
    print(f"  backup agendado: {t['backup_agendado_s']:.1f} s")
    print(f"  RTO: {t['rto_s']:.1f} s (alvo < {result['rto_target_s']} s)")
    print(f"  payload público: {'byte-idêntico' if result['payload_identical'] else 'DIFERENTE'} "
          f"({result['public_items']} itens)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_ata(repo, result), encoding="utf-8", newline="\n")
    print(f"  ata: {out}")
    if not result["ok"]:
        print("DRILL FALHOU")
        return 1
    print("DRILL OK — RTO cumprido")
    return 0


if __name__ == "__main__":
    sys.exit(main())

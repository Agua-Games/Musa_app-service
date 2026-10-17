"""M3.1 runner: boot `musa-build serve` on a DISPOSABLE copy of a client repo,
run the synthetic suites, log JSONL per action (ADR 0016), write a summary.

Suites: personas (M3.1), misuse generator (M3.2), edge battery (M4.5) or all.

Nothing is committed, deployed or uploaded: the copy lives in a temp dir, the
overlay lives in another temp dir, and uploads never leave the machine
(restrictions 2 and 4 of docs/M3_plano.md).

Usage (from the platform repo root):

    python -m beta.run_beta --repo H:\\Musa_app-service\\DemoMuseum --seed 42
    python -m beta.run_beta --repo <repo> --suite edge
    python -m beta.run_beta --repo <repo> --routines diaria --no-build-check
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from .client import ApiClient
from . import invariants as inv
from .edge import EdgeRunner
from .harness import BUILDER_DIR, ServeHarness
from .misuse import MisuseRunner
from .personas import SCOPES, ROUTINES, make_personas

PLATFORM_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PLATFORM_ROOT / "source"  # the generic frontend (image: /app/frontend)

IGNORE = shutil.ignore_patterns(".git", ".musa", "_site", "node_modules", "__pycache__")


def run(repo: Path, seed: int, routines: list[str], out_dir: Path,
        build_check: bool, suite: str = "personas") -> int:
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-seed{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / f"beta-log-{run_id}.jsonl"

    all_events = []
    tmpdir = tempfile.mkdtemp(prefix="musa-beta-")
    harness: ServeHarness | None = None
    try:
        root = Path(tmpdir)
        work_repo = root / "repo"
        data_dir = root / "overlay"
        shutil.copytree(repo, work_repo, ignore=IGNORE)

        museum_cfg = json.loads((work_repo / "museum.config.json").read_text(encoding="utf-8"))
        museum_tier = museum_cfg.get("entitlements", {}).get("tier", "bronze")
        token = f"beta-token-{seed}"

        harness = ServeHarness(work_repo, data_dir, token=token, log_dir=root / "logs")
        client = harness.boot()

        try:
            if suite in ("personas", "all"):
                for persona in make_personas(client, seed, run_id, museum_tier):
                    login = client.login(persona.email, token)
                    if not login.ok:
                        print(f"FATAL: login failed for {persona.email}", file=sys.stderr)
                        return 2
                    for cenario in routines:
                        if cenario not in SCOPES[persona.email]:
                            continue
                        getattr(persona, ROUTINES[cenario])()
                    if build_check:
                        res = inv.check_build_green(work_repo, FRONTEND_DIR,
                                                    root / "site-out", BUILDER_DIR)
                        persona._record("sessao", "build-verde", str(work_repo),
                                        "ok" if res.ok else "falha", 0.0, res.detail,
                                        invariantes=[res])
                    all_events.extend(persona.events)

            if suite in ("misuse", "all"):
                login = client.login("misuse@demo", token)
                if not login.ok:
                    print("FATAL: login failed for misuse@demo", file=sys.stderr)
                    return 2
                runner = MisuseRunner(client, random.Random(f"{seed}:misuse"),
                                      run_id, museum_tier)
                all_events.extend(runner.run_all())

            if suite in ("edge", "all"):
                login = client.login("edge@demo", token)
                if not login.ok:
                    print("FATAL: login failed for edge@demo", file=sys.stderr)
                    return 2
                edge = EdgeRunner(harness, client, random.Random(f"{seed}:edge"),
                                  run_id, museum_tier, work_repo, BUILDER_DIR,
                                  FRONTEND_DIR, root)
                all_events.extend(edge.run_all())
        finally:
            harness.stop()
    finally:
        # On Windows the SQLite overlay file can stay locked for a few
        # hundred ms after the serve subprocess dies — retry, then give up
        # without masking the run's result.
        for _ in range(10):
            try:
                shutil.rmtree(tmpdir, ignore_errors=False)
                break
            except PermissionError:
                time.sleep(0.5)
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)

    with log_path.open("w", encoding="utf-8") as fh:
        for ev in all_events:
            fh.write(json.dumps(ev.as_dict(), ensure_ascii=False) + "\n")

    total = len(all_events)
    falhas = [e for e in all_events if e.veredito == "reprova"]
    gaps = [e for e in all_events if e.resultado == "achado-gap"]
    report = {
        "run_id": run_id,
        "seed": seed,
        "repo": str(repo),
        "suite": suite,
        "routines": routines,
        "eventos": total,
        "reprovacoes": len(falhas),
        "achados_gap": len({e.detalhe.split(":")[0] for e in gaps}),
        "latencia_media_ms": round(sum(e.latencia_ms for e in all_events) / max(total, 1), 1),
    }
    report_path = out_dir / f"beta-report-{run_id}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"run_id: {run_id}")
    print(f"events: {total} | failures: {len(falhas)} | gap findings: {len(gaps)} "
          f"({report['achados_gap']} distinct)")
    print(f"log:    {log_path}")
    print(f"report: {report_path}")
    if falhas:
        for e in falhas:
            print(f"  REPROVA [{e.persona}/{e.cenario}] {e.acao} {e.alvo}: {e.detalhe}")
        return 1
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="beta.run_beta")
    p.add_argument("--repo", required=True, help="client repository root (e.g. the DemoMuseum)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--routines", default="all",
                   choices=["diaria", "semanal", "pontual", "all"])
    p.add_argument("--out", default=str(PLATFORM_ROOT / "beta" / "out"))
    p.add_argument("--no-build-check", action="store_true",
                   help="skip the slower build-green invariant (per-session)")
    p.add_argument("--suite", default="personas",
                   choices=["personas", "misuse", "edge", "all"],
                   help="personas (M3.1), misuse generator (M3.2), edge battery (M4.5) or all")
    args = p.parse_args(argv)

    routines = ["diaria", "semanal", "pontual"] if args.routines == "all" else [args.routines]
    return run(Path(args.repo), args.seed, routines, Path(args.out),
               build_check=not args.no_build_check, suite=args.suite)


if __name__ == "__main__":
    raise SystemExit(main())

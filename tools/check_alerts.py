"""M4.4 — SLO alert check over a serve JSONL log (thin CLI wrapper).

The rules live, tested, in builder/musa_build/alerts.py. Exit 1 when any
rule fires, so a scheduler (cron/Task Scheduler/CI) can turn it into a
notification — the channels are documented in docs/runbook.md §Alertas.

Usage:  python tools/check_alerts.py <serve-log.jsonl> [--custo-dia 0.50]
            [--rejeicoes-dia 10] [--assets-dia 50000]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "builder"))

from musa_build.alerts import (  # noqa: E402
    DEFAULT_ASSETS_DIA,
    DEFAULT_CUSTO_DIA_USD,
    DEFAULT_REJEICOES_DIA,
    scan_log,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", help="serve JSONL log file (or - for stdin)")
    parser.add_argument("--custo-dia", type=float, default=DEFAULT_CUSTO_DIA_USD,
                        help=f"assistant daily cost ceiling in USD (default {DEFAULT_CUSTO_DIA_USD})")
    parser.add_argument("--rejeicoes-dia", type=int, default=DEFAULT_REJEICOES_DIA,
                        help=f"422-per-day ceiling on writes (default {DEFAULT_REJEICOES_DIA})")
    parser.add_argument("--assets-dia", type=int, default=DEFAULT_ASSETS_DIA,
                        help=f"asset downloads per day band (default {DEFAULT_ASSETS_DIA})")
    args = parser.parse_args(argv)

    if args.log == "-":
        lines = sys.stdin.read().splitlines()
    else:
        path = Path(args.log)
        if not path.is_file():
            print(f"ERROR: {path} not found")
            return 2
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    alerts = scan_log(lines, custo_dia=args.custo_dia,
                      rejeicoes_dia=args.rejeicoes_dia,
                      assets_dia=args.assets_dia)
    if not alerts:
        print(f"sem alertas — {len(lines)} linhas analisadas")
        return 0
    for alert in alerts:
        print(f"ALERTA: {alert}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

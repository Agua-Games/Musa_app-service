"""M4.4 — SLO alert rules over the serve JSONL logs (spec §8.2).

The serve emits one JSON object per line (BuildLogger, stderr). Ops collects
those lines; this module applies the alert thresholds derived from the SLO
table (docs/M3_slos.md) and returns plain-Portuguese alert strings. The CLI
wrapper is tools/check_alerts.py.

Rules (per UTC day, per tenant log):

- **custo-assistente**: summed ``cost_usd_estimate`` of ``assistant_ask``
  events above the daily ceiling (default US$ 0.50 ≈ 1.200 asks at the
  measured ~US$ 0.0004/ask — anything beyond that is anomaly or abuse);
- **cota-estourada**: any ``assistant_ask`` with outcome ``quota_exceeded`` —
  the daily token quota tripped; someone is pushing the tenant past budget;
- **cards-rejeitados**: 422 answers on POST /items|/collections above the
  daily ceiling (the build SLO is ZERO rejected cards; a trickle of curator
  typos is normal, a flood is a broken integration or probing);
- **egress-assets**: asset downloads above the daily band (initial 50k —
  tune with the first real traffic; R2 egress is free, the signal is bots);
- **5xx**: any server error answer, any volume — always worth a look.

Thresholds are deliberately arguments: they are starting points to tune per
tenant, not contractual SLO numbers (those live in docs/M3_slos.md).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

DEFAULT_CUSTO_DIA_USD = 0.50
DEFAULT_REJEICOES_DIA = 10
DEFAULT_ASSETS_DIA = 50_000


@dataclass
class _Day:
    custo: float = 0.0
    quota_exceeded: int = 0
    rejeicoes: int = 0
    assets: int = 0
    server_errors: list = field(default_factory=list)


def scan_log(lines: Iterable[str], *, custo_dia: float = DEFAULT_CUSTO_DIA_USD,
             rejeicoes_dia: int = DEFAULT_REJEICOES_DIA,
             assets_dia: int = DEFAULT_ASSETS_DIA) -> list[str]:
    """Apply every rule to the log lines; returns the triggered alerts."""
    days: dict[str, _Day] = defaultdict(_Day)
    for line in lines:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        day = str(event.get("ts", ""))[:10] or "<sem-data>"
        bucket = days[day]
        kind = event.get("event")
        if kind == "assistant_ask":
            bucket.custo += float(event.get("cost_usd_estimate") or 0.0)
            if event.get("outcome") == "quota_exceeded":
                bucket.quota_exceeded += 1
        elif kind == "api_request":
            status = int(event.get("status") or 0)
            path = str(event.get("path") or "")
            method = str(event.get("method") or "")
            if status >= 500:
                bucket.server_errors.append(f"{method} {path} -> {status}")
            elif path.startswith("/assets/") and status == 200:
                bucket.assets += 1
            elif (method == "POST" and status == 422
                  and path in ("/items", "/collections")):
                bucket.rejeicoes += 1

    alerts: list[str] = []
    for day in sorted(days):
        bucket = days[day]
        if bucket.custo > custo_dia:
            alerts.append(
                f"custo do assistente em {day}: US$ {bucket.custo:.4f} — acima do "
                f"teto de US$ {custo_dia:.2f}/dia (anomalia ou abuso; ver outcomes "
                "e ips_hash no log)")
        if bucket.quota_exceeded:
            alerts.append(
                f"cota diária do assistente estourou em {day}: "
                f"{bucket.quota_exceeded} ask(s) recusados por quota_exceeded")
        if bucket.rejeicoes > rejeicoes_dia:
            alerts.append(
                f"{bucket.rejeicoes} cards rejeitados (422) em {day} — o SLO de "
                f"produção é 0; acima de {rejeicoes_dia}/dia indica integração "
                "quebrada ou sondagem")
        if bucket.assets > assets_dia:
            alerts.append(
                f"{bucket.assets} downloads de assets em {day} — acima da faixa "
                f"de {assets_dia}/dia; verificar bots/egress (R2 não cobra "
                "egress, mas o sinal é de abuso)")
        if bucket.server_errors:
            sample = ", ".join(bucket.server_errors[:3])
            alerts.append(
                f"{len(bucket.server_errors)} resposta(s) 5xx em {day} "
                f"({sample}) — erro de servidor nunca é ruído")
    return alerts

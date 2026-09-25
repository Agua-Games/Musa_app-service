"""Structured build logging (M1.5): every decision, one JSON line.

Correlation ids follow the chain ``tenant → build → asset``:

    {"ts": "...", "level": "info", "tenant": "demo-museum", "build": "b-20260925-a1b2c3d4",
     "event": "gate", "asset": "ronda-noturna", "included": false, "reasons": [...]}

The logger buffers events in memory and flushes to ``<out>/build-log.jsonl`` —
buffered because the build wipes and recreates ``out`` mid-run. With
``MUSA_LOG=stderr`` every line is also mirrored to stderr in real time, so CI
collects it even when the run never reaches the flush. A whole build must be
reproducible from these lines alone (the M1.5 verification criterion).
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def new_build_id() -> str:
    return f"b-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8]}"


class BuildLogger:
    """JSONL logger with tenant/build/asset correlation ids."""

    def __init__(self, tenant: str, *, build_id: str | None = None):
        self.tenant = tenant or "<unknown>"
        self.build_id = build_id or new_build_id()
        self.events: list[dict] = []
        self._mirror = os.environ.get("MUSA_LOG", "").lower() == "stderr"

    def log(self, event: str, *, level: str = "info", asset: str | None = None, **fields) -> None:
        line = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": level,
            "tenant": self.tenant,
            "build": self.build_id,
            "event": event,
        }
        if asset is not None:
            line["asset"] = asset
        line.update(fields)
        self.events.append(line)
        if self._mirror:
            print(json.dumps(line, ensure_ascii=False), file=sys.stderr)

    def warning(self, event: str, **fields) -> None:
        self.log(event, level="warning", **fields)

    def error(self, event: str, **fields) -> None:
        self.log(event, level="error", **fields)

    def flush(self, out: Path) -> Path:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "build-log.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for line in self.events:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        return path


def get_logger(report) -> BuildLogger:
    """The logger attached to a report; creates and attaches one on demand."""
    logger = getattr(report, "_logger", None)
    if logger is None:
        logger = BuildLogger(report.museum_id)
        report._logger = logger
    return logger

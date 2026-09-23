"""Build report (M0.6): what went in, what stayed out, and why.

The report is the content debugger required by the roadmap: "why is this piece
not on the site?" must be answerable in one line, without an investigation.
It is emitted as JSON (machine) and Markdown (human) on every run — including
failed runs, where it carries the contract violations.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Entry:
    kind: str  # "collection" | "item"
    ref: str   # collection id or asset_id
    included: bool
    reasons: list[str] = field(default_factory=list)


@dataclass
class BuildReport:
    museum_id: str
    builder_version: str
    contract_version: str
    entitled_tier: str
    modules: list[str] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def ok(self) -> bool:
        return not self.errors

    def counts(self) -> dict:
        items = [e for e in self.entries if e.kind == "item"]
        return {
            "items_total": len(items),
            "items_included": sum(1 for e in items if e.included),
            "items_excluded": sum(1 for e in items if not e.included),
        }

    def to_dict(self) -> dict:
        return {
            "result": "success" if self.ok else "failure",
            "museum": self.museum_id,
            "builder_version": self.builder_version,
            "contract_version": self.contract_version,
            "entitled_tier": self.entitled_tier,
            "modules": self.modules,
            "started_at": self.started_at,
            "counts": self.counts(),
            "entries": [vars(e) for e in self.entries],
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def to_markdown(self) -> str:
        c = self.counts()
        lines = [
            f"# Build report — {self.museum_id}",
            "",
            f"- result: **{'success' if self.ok else 'failure'}**",
            f"- builder: musa-app {self.builder_version} · contract v{self.contract_version}",
            f"- entitled tier: {self.entitled_tier} · modules: {', '.join(self.modules) or '(none)'}",
            f"- items: {c['items_included']} published / {c['items_excluded']} excluded / {c['items_total']} total",
            f"- started: {self.started_at}",
            "",
        ]
        if self.errors:
            lines += ["## Errors (the build failed)", ""]
            lines += [f"- {e}" for e in self.errors]
            lines.append("")
        if self.warnings:
            lines += ["## Warnings", ""]
            lines += [f"- {w}" for w in self.warnings]
            lines.append("")
        lines += ["## Content decisions", "", "| record | kind | decision | why |", "|---|---|---|---|"]
        for e in self.entries:
            decision = "INCLUDED" if e.included else "EXCLUDED"
            why = "; ".join(e.reasons) if e.reasons else "—"
            lines.append(f"| {e.ref} | {e.kind} | {decision} | {why} |")
        lines.append("")
        return "\n".join(lines)

    def write(self, out_dir: Path) -> None:
        (out_dir / "build-report.json").write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "build-report.md").write_text(self.to_markdown(), encoding="utf-8")

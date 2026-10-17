"""Read a log **selectively**, and keep the folder it lands in from growing forever.

Adapted for the MUSA platform repo (2026-10-17) from a tool the owner brought
from another repo (scratch/owner/read.py — the .toml files there belong to
that repo's tool registry, which does not exist here).

**Why this exists**: an agent reads a log to diagnose, and reading *all* of it
is the expensive way — a build log is thousands of lines of the same error,
and a thousand identical lines say exactly what one says. Two verbs:

* **`read`** takes the **tail**, and **collapses repeated lines**: a line is
  normalised (timestamps, durations, hex addresses, paths and bare numbers
  become placeholders), lines that normalise the same are grouped, and each
  group is printed **once with its count**. So "the same error 400 times"
  costs one line, and a *distinct* error always survives.
* **`sweep`** keeps a log folder bounded: it looks at files matching
  `--pattern` (default `*.log`) **in the folder it is pointed at, and only
  there**, and when their **total** size passes a ceiling it removes the
  oldest, reporting what it removed.

Both are deliberately *unable* to do more: `read` never modifies anything,
and `sweep` only ever deletes matching files inside the one folder given,
never a directory, and never anything outside it.

Usage:

    python tools/logread.py read --file beta/out/beta-log-XXX.jsonl [--lines 400] [--grep erro] [--show 40]
    python tools/logread.py sweep --folder beta/out --pattern "*.jsonl" --max-mb 500 [--dry_run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

#: What makes two lines "the same line". Each of these differs between two
#: occurrences of one error and carries no information when it does: a
#: timestamp, a duration, a path that moves, an address, an id, a bare number.
NOISE = (
    (re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?"), "<time>"),
    (re.compile(r"\d+\.\d+\s*(?:s|ms|seconds?)"), "<took>"),
    (re.compile(r"0x[0-9a-fA-F]+"), "<addr>"),
    (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "<hex>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"[A-Za-z]:\\[^\s\"']+"), "<path>"),
    # POSIX paths (CI logs are Linux) — two or more segments, so a lone
    # "/health" route survives but "/work/client/content/..." collapses.
    (re.compile(r"(?<![\w:])/(?:[\w.\-]+/)+[\w.\-]+"), "<path>"),
    (re.compile(r"\s+"), " "),
)


def shape_of(line: str) -> str:
    """The line with everything that varies between two occurrences of one message taken out."""
    held = line.strip()
    for pattern, instead in NOISE:
        held = pattern.sub(instead, held)
    return held


def collapsed(lines: list[str]) -> list[tuple[str, int, str]]:
    """The lines as (a first-seen example, how many, its shape), in the order first seen."""
    seen: OrderedDict[str, list] = OrderedDict()
    for line in lines:
        if not line.strip():
            continue
        shape = shape_of(line)
        if shape in seen:
            seen[shape][1] += 1
        else:
            seen[shape] = [line.rstrip(), 1]
    return [(example, count, shape) for shape, (example, count) in seen.items()]


def read(args: argparse.Namespace) -> int:
    where = Path(args.file)
    if not where.is_file():
        print(f"there is no log at {where}", file=sys.stderr)
        print(json.dumps({"ok": False, "tool": "logread/read", "error": "no such log"}))
        return 3
    # The tail, and only the tail: a log's *end* is where the failure is, and
    # reading a 200 MB file to find it is the cost this exists to avoid.
    with where.open("r", encoding="utf-8", errors="replace") as stream:
        tail = list(stream)[-args.lines:]
    if args.grep:
        pattern = re.compile(args.grep, re.IGNORECASE)
        tail = [one for one in tail if pattern.search(one)]
    groups = collapsed(tail)
    for example, count, _ in groups[: args.show]:
        prefix = f"{count:>5}x " if count > 1 else "      "
        print(f"{prefix}{example[:220]}")
    if len(groups) > args.show:
        print(f"      ... and {len(groups) - args.show} more distinct line(s)")
    # The machine-readable tail is a SUMMARY by default — echoing every line
    # as JSON would double the token cost this tool exists to save. --json
    # asks for the full per-line echo (shape included).
    report = {"ok": True, "tool": "logread/read", "file": str(where),
              "read": len(tail), "distinct": len(groups)}
    if args.json:
        report["lines"] = [{"count": count, "says": example, "shape": shape}
                           for example, count, shape in groups[: args.show]]
    print("JSON " + json.dumps(report, ensure_ascii=False))
    return 0


def sweep(args: argparse.Namespace) -> int:
    where = Path(args.folder)
    if not where.is_dir():
        print(f"there is no folder at {where}", file=sys.stderr)
        print(json.dumps({"ok": False, "tool": "logread/sweep", "error": "no such folder"}))
        return 3
    # **Only files matching the pattern, only here, never a directory.** A
    # sweep that walked a tree would be a delete nobody asked for.
    found = sorted((one for one in where.glob(args.pattern) if one.is_file()),
                   key=lambda one: one.stat().st_mtime)
    before = sum(one.stat().st_size for one in found)
    ceiling = int(args.max_mb * 1_000_000)
    removed: list[dict] = []
    if before > ceiling and not args.dry_run:
        for one in found:
            if before <= ceiling:
                break
            size = one.stat().st_size
            one.unlink()
            removed.append({"file": str(one), "bytes": size})
            before -= size
    left = sum(one.stat().st_size for one in found if one.exists())
    report = {"ok": True, "tool": "logread/sweep", "folder": str(where),
              "pattern": args.pattern, "files": len(found),
              "total_bytes": left, "was_bytes": sum(one["bytes"] for one in removed) + left,
              "ceiling_bytes": ceiling, "removed": removed, "dry_run": bool(args.dry_run)}
    print(f"{len(found)} log(s), {report['total_bytes']:,} bytes left, ceiling {ceiling:,}")
    for one in removed:
        print(f"   removed {Path(one['file']).name} ({one['bytes']:,} bytes)")
    if left > ceiling:
        print("   still over the ceiling: something in this folder does not match the pattern, or a log is held open")
    print("JSON " + json.dumps(report, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read a log by its distinct lines, and keep its folder bounded")
    sub = parser.add_subparsers(dest="verb", required=True)
    one = sub.add_parser("read", help="the tail, with repeated lines collapsed to one sample each")
    one.add_argument("--file", required=True, help="the log to read")
    one.add_argument("--lines", type=int, default=400, help="how much of the tail to look at")
    one.add_argument("--grep", default="", help="a pattern to keep only matching lines")
    one.add_argument("--show", type=int, default=40, help="how many distinct lines to print")
    one.add_argument("--json", action="store_true",
                     help="append the full per-line JSON echo (default: summary only)")
    two = sub.add_parser("sweep", help="drop the oldest log files in ONE folder when their total passes a ceiling")
    two.add_argument("--folder", required=True, help="the folder logs land in -- and the only folder looked at")
    two.add_argument("--pattern", default="*.log",
                     help="glob of what counts as a log here (e.g. '*.jsonl' for beta/out)")
    two.add_argument("--max-mb", type=float, default=500.0, help="the total ceiling, in decimal megabytes")
    two.add_argument("--dry_run", action="store_true", help="report what would go, and remove nothing")
    args = parser.parse_args(argv)
    return read(args) if args.verb == "read" else sweep(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

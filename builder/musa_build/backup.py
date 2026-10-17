"""M4.4 — local backup of the write overlay (``.musa/state.db``) + restore.

The client repository is the seed (git-versioned — its RPO is GitHub's).
Day-to-day admin edits made through the API live ONLY in the overlay SQLite;
without a backup their RPO is "until the next commit" (the M3.6 debt, SLO
table §RPO/RTO). This module produces a consistent, verifiable local backup
and a restore that refuses the wrong museum or a corrupted copy before
writing a single byte.

A backup directory looks like::

    musa-backup-<museum_id>-<UTC yymmddThhmmssZ>/
        state.db        consistent copy (SQLite backup API — safe against a
                        LIVE server: it takes the proper shared lock)
        manifest.json   museum_id, created, builder_version, record counts,
                        sha256 of state.db

Restore checks manifest ↔ museum.id and sha256 ↔ bytes, moves any existing
overlay aside (never destroys), copies the backup in, and then BOOTS THE APP
as the final proof — a restore that cannot boot is reported as failed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .build import load_config


class BackupError(Exception):
    """A backup/restore precondition failed (nothing to back up, wrong
    museum, corrupted copy, …). The CLI turns this into exit 2."""


def _overlay_path(repo: Path, data_dir: Path | None) -> Path:
    base = Path(data_dir) if data_dir else Path(repo) / ".musa"
    return base / "state.db"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(db_path: Path) -> dict:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        collections = conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0]
    finally:
        conn.close()
    return {"items": items, "collections": collections}


def create_backup(repo: Path, *, data_dir: Path | None = None,
                  out_dir: Path) -> Path:
    """Consistent copy of the overlay + manifest. Returns the backup dir."""
    repo = Path(repo)
    source = _overlay_path(repo, data_dir)
    if not source.is_file():
        raise BackupError(
            f"no overlay at {source} — this instance has no admin edits to back up")
    museum_id = (load_config(repo).get("museum") or {}).get("id", "<unknown>")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(out_dir) / f"musa-backup-{museum_id}-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    target = backup_dir / "state.db"
    src_conn = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst_conn = sqlite3.connect(target)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    manifest = {
        "museum_id": museum_id,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "builder_version": __version__,
        "source": str(source),
        "counts": _counts(target),
        "sha256": _sha256(target),
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return backup_dir


def restore_backup(repo: Path, *, backup_dir: Path,
                   data_dir: Path | None = None) -> dict:
    """Verify, install and boot-prove a backup. Returns the post-restore counts
    (seed + overlay, as the running app sees them)."""
    repo = Path(repo)
    backup_dir = Path(backup_dir)
    manifest_path = backup_dir / "manifest.json"
    backup_db = backup_dir / "state.db"
    if not manifest_path.is_file() or not backup_db.is_file():
        raise BackupError(f"{backup_dir} is not a backup directory "
                          "(needs manifest.json and state.db)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    museum_id = (load_config(repo).get("museum") or {}).get("id", "<unknown>")
    if manifest.get("museum_id") != museum_id:
        raise BackupError(
            f"backup belongs to museum {manifest.get('museum_id')!r}, this repo is "
            f"{museum_id!r} — refusing to restore the wrong tenant's data")
    digest = _sha256(backup_db)
    if digest != manifest.get("sha256"):
        raise BackupError(
            f"sha256 mismatch: the backup copy is corrupted "
            f"(manifest {manifest.get('sha256')}, file {digest}) — do not restore")

    target = _overlay_path(repo, data_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        # Never destroy: the current overlay moves aside, restorable by hand.
        aside = target.with_suffix(f".before-restore-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
        shutil.move(str(target), str(aside))
    shutil.copy2(backup_db, target)

    # The final proof is the app booting on the restored state.
    from .serve import create_app

    app = create_app(repo, data_dir=target.parent)
    try:
        state = app.state.serve
        return {
            "museum_id": state.museum_id,
            "total_collections": len(state.all_collections),
            "total_items": len(state.all_items),
            "public_items": len(state.items),
            "restored_from": str(backup_dir),
            "backup_created": manifest.get("created"),
        }
    finally:
        app.state.serve.store.close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="musa-build backup",
        description="Local backup/restore of the write overlay (M4.4).",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    for name, helptext in (("backup", "copy the overlay + write a manifest"),
                           ("restore", "verify, install and boot-prove a backup")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--repo", required=True, help="client repository root")
        p.add_argument("--data-dir", default=None,
                       help="overlay location (default: <repo>/.musa)")
    sub.choices["backup"].add_argument("--out", required=True,
                                       help="directory the backup folder is created in")
    sub.choices["restore"].add_argument("--from", dest="source", required=True,
                                        help="the backup directory to restore from")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir) if args.data_dir else None
    try:
        if args.action == "backup":
            out = create_backup(Path(args.repo), data_dir=data_dir, out_dir=Path(args.out))
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            counts = manifest["counts"]
            print(f"BACKUP OK — {out} "
                  f"({counts['items']} items, {counts['collections']} collections)")
        else:
            result = restore_backup(Path(args.repo), backup_dir=Path(args.source),
                                    data_dir=data_dir)
            print(f"RESTORE OK — {result['museum_id']}: {result['total_items']} items and "
                  f"{result['total_collections']} collections visible to the app "
                  f"(boot-proved), from backup of {result['backup_created']}")
    except BackupError as exc:
        print(f"ERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

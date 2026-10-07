"""Asset upload to object storage (M1.3, ADR 0009): ``musa-build upload``.

Scans the client repository's cards for LOCAL asset references (image,
model_primary, collection covers), uploads each file to the tenant's bucket
over the S3-compatible API, and rewrites the card to the public URL — the
repository keeps the URL, never the binary, so it shrinks over time instead
of growing (the M0 lesson).

Configuration lives in the client repo's museum.config.json:

    "storage": {
      "provider": "r2",
      "bucket": "musa-assets-<museum-id>",
      "endpoint": "https://<account-id>.r2.cloudflarestorage.com",
      "assetsBaseUrl": "https://pub-<hash>.r2.dev"
    }

Credentials come from the environment (never from the repo):
MUSA_R2_ACCESS_KEY_ID / MUSA_R2_SECRET_ACCESS_KEY (AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY are honored as fallback).
"""

import json
import mimetypes
import os
from pathlib import Path

from . import __version__
from .build import BuildFailure, _is_url, load_config, read_content
from .log import get_logger
from .report import BuildReport

UPLOADABLE_ITEM_FIELDS = ("image", "model_primary")


def storage_config(config: dict) -> dict:
    """Normalize the storage block; missing pieces are a config error."""
    storage = config.get("storage") or {}
    missing = [k for k in ("bucket", "endpoint", "assetsBaseUrl") if not storage.get(k)]
    if missing:
        raise ValueError(f"museum.config.json: storage.{', storage.'.join(missing)} required for upload")
    return storage


def make_s3_client(storage: dict):
    """S3-compatible client (R2 today; same interface for Azure/B2 later)."""
    import boto3

    access_key = os.environ.get("MUSA_R2_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("MUSA_R2_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise ValueError(
            "set MUSA_R2_ACCESS_KEY_ID and MUSA_R2_SECRET_ACCESS_KEY "
            "(the R2 API token scoped to the bucket) — credentials never live in the repo"
        )
    return boto3.client(
        "s3",
        endpoint_url=storage["endpoint"],
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",  # R2 ignores the region but requires one
    )


def _public_url(storage: dict, key: str) -> str:
    return f"{storage['assetsBaseUrl'].rstrip('/')}/{key}"


def _put(s3, storage: dict, key: str, path: Path, logger, owner: str) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    s3.put_object(
        Bucket=storage["bucket"],
        Key=key,
        Body=path.read_bytes(),
        ContentType=content_type,
        CacheControl="public, max-age=31536000, immutable",
    )
    logger.log("asset_upload", asset=owner, key=key, bytes=path.stat().st_size)
    return _public_url(storage, key)


def upload_assets(repo: Path, *, s3=None) -> BuildReport:
    """Upload local card assets and rewrite the cards to public URLs.

    Returns a report whose entries list what moved; the repo is modified in
    place (cards rewritten) and the change is meant to be committed.
    """
    repo = Path(repo)
    config = load_config(repo)
    museum_cfg = config.get("museum") or {}
    report = BuildReport(
        museum_id=museum_cfg.get("id", "<unknown>"),
        builder_version=__version__,
        contract_version="upload",
        entitled_tier=(config.get("entitlements") or {}).get("tier", "<unknown>"),
    )
    log = get_logger(report)
    log.log("upload_start", repo=str(repo))

    try:
        storage = storage_config(config)
    except ValueError as exc:
        report.fail(str(exc))
        raise BuildFailure(report)
    if s3 is None:
        try:
            s3 = make_s3_client(storage)
        except ValueError as exc:
            report.fail(str(exc))
            raise BuildFailure(report)

    collections, items, _site = read_content(repo, report)
    if report.errors:
        raise BuildFailure(report)

    uploaded = skipped = 0

    def handle(owner_dir: Path, record: dict, field: str, key_prefix: str) -> bool:
        """Upload one field's file if it is a local reference. Returns True if uploaded."""
        value = record.get(field)
        if not value or _is_url(value):
            return False
        source = owner_dir / value
        if not source.is_file():
            report.warn(f"{record.get('asset_id', key_prefix)}: {field} {value!r} not found — left as-is")
            return False
        key = f"{key_prefix}/{value}"
        url = _put(s3, storage, key, source, log, record.get("asset_id", key_prefix))
        record[field] = url
        return True

    for collection in collections:
        collection_dir = collection["_dir"]
        if handle(collection_dir, collection, "cover", collection["id"]):
            uploaded += 1
            (collection_dir / "collection.json").write_text(
                json.dumps({k: v for k, v in collection.items() if not k.startswith("_")},
                           ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            log.log("card_rewrite", path=f"content/{collection['id']}/collection.json")

    for item in items:
        item_dir = item["_dir"]
        changed = False
        for field in UPLOADABLE_ITEM_FIELDS:
            prefix = f"{item['colecao']}/{item['asset_id']}"
            changed = handle(item_dir, item, field, prefix) or changed
        if changed:
            uploaded += 1
            (item_dir / "card.json").write_text(
                json.dumps({k: v for k, v in item.items() if not k.startswith("_")},
                           ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            log.log("card_rewrite", path=f"content/{item['colecao']}/{item['asset_id']}/card.json")
        else:
            skipped += 1

    log.log("upload_end", uploaded=uploaded, untouched=skipped)
    print(f"UPLOAD OK — {uploaded} record(s) now reference the bucket, {skipped} untouched")
    print("next: commit the rewritten cards (binaries may leave the repo) and push")
    return report

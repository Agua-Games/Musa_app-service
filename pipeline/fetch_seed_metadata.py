"""Fetch real object metadata from the Met Open Access API (M2.1).

The Met collection API is free and keyless (https://metmuseum.github.io/).
We sample object IDs from a few departments with a fixed seed and cache the
results under pipeline/corpus/seed/ so re-runs resume where they stopped.

Usage:
    python fetch_seed_metadata.py --target 450
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

import requests

API = "https://collectionapi.metmuseum.org/public/collection/v1"
# European Paintings (11), European Sculpture & Decorative Arts (12),
# Egyptian Art (10), Greek & Roman Art (13), Asian Art (6).
DEPARTMENTS = "11|12|10|13|6"
CACHE = Path(__file__).parent / "corpus" / "seed" / "met-objects.json"

FIELDS = (
    "objectID", "title", "artistDisplayName", "objectDate", "medium",
    "dimensions", "department", "objectName", "culture", "period",
)


def fetch_json(url: str, tries: int = 4) -> dict:
    for attempt in range(tries):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # transient network blips / Met rate limiting (403)
            if attempt == tries - 1:
                raise
            wait = 5 * (attempt + 1)
            time.sleep(wait)
            print(f"  retry {attempt + 1} in {wait}s after {exc}", file=sys.stderr)
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=450)
    args = parser.parse_args()

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache: dict[str, dict] = {}
    if CACHE.exists():
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
        print(f"cache: {len(cache)} object(s) already fetched")

    listing = fetch_json(f"{API}/objects?departmentIds={DEPARTMENTS}")
    ids = listing["objectIDs"]
    random.Random(20261008).shuffle(ids)  # fixed seed: reproducible sample
    wanted = [str(i) for i in ids[: args.target]]
    missing = [i for i in wanted if i not in cache]
    print(f"target {args.target}; fetching {len(missing)} new object(s)")

    failed = 0
    for n, object_id in enumerate(missing, 1):
        try:
            data = fetch_json(f"{API}/objects/{object_id}")
        except Exception as exc:
            failed += 1
            print(f"  SKIP {object_id}: {exc}", file=sys.stderr)
            continue
        cache[object_id] = {k: data.get(k) or "" for k in FIELDS}
        if n % 25 == 0 or n == len(missing):
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {n}/{len(missing)} fetched (cached)")
        time.sleep(0.12)  # be polite: ~8 req/s

    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"SEED OK — {len(cache)} object(s) cached at {CACHE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

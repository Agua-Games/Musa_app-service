"""Batch OCR over the corpus — headless, resumable, failure-isolating (M2.2).

Scans pipeline/corpus/images/*.jpg, writes pipeline/corpus/ocr/<asset_id>.json
per card and one JSONL line per card to corpus/ocr-log.jsonl (correlation:
card → engine → seconds → status). A failed card lands in corpus/ocr/failed/
with the reason and NEVER aborts the batch. Re-running resumes where it stopped.

Usage (venv python):
    .venv/Scripts/python.exe run_ocr.py [--offset 0] [--limit 50]
"""

import argparse
import json
import sys
import time
from pathlib import Path

from ocr_engine import make_engine

ROOT = Path(__file__).parent
IMG_DIR = ROOT / "corpus" / "images"
OCR_DIR = ROOT / "corpus" / "ocr"
FAILED_DIR = OCR_DIR / "failed"
LOG = ROOT / "corpus" / "ocr-log.jsonl"


def log(entry: dict) -> None:
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    images = sorted(IMG_DIR.glob("*.jpg"))
    batch = images[args.offset : (None if args.limit is None else args.offset + args.limit)]
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)

    engine = None  # lazy: model load happens once, on first use
    done = failed = skipped = 0
    started_all = time.perf_counter()
    for path in batch:
        out = OCR_DIR / f"{path.stem}.json"
        if out.exists() or (FAILED_DIR / f"{path.stem}.json").exists():
            skipped += 1
            continue
        if engine is None:
            print("loading OCR engine (first run downloads models)...", flush=True)
            engine = make_engine("docling")
        try:
            result = engine.run(path)
        except Exception as exc:
            failed += 1
            (FAILED_DIR / f"{path.stem}.json").write_text(
                json.dumps({"asset_id": path.stem, "error": f"{type(exc).__name__}: {exc}"},
                           ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            log({"card": path.stem, "engine": engine.name, "status": "failed",
                 "error": f"{type(exc).__name__}: {exc}"})
            print(f"  FAILED {path.stem}: {exc}", flush=True)
            continue
        done += 1
        result["asset_id"] = path.stem
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        log({"card": path.stem, "engine": result["engine"], "status": "ok",
             "seconds": result["seconds"], "blocks": len(result["blocks"]),
             "chars": len(result["text"])})
        print(f"  ok {path.stem} ({result['seconds']}s, {len(result['blocks'])} blocks)", flush=True)

    total = round(time.perf_counter() - started_all, 1)
    print(f"OCR BATCH — {done} done, {failed} failed, {skipped} skipped (resume), "
          f"{total}s wall; log: {LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

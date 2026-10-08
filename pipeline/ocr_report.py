"""OCR batch report (M2.2 verification): totals, failures, char recall vs ground truth.

Reads corpus/ocr-log.jsonl + corpus/ocr/*.json + corpus/ground-truth/*.json and
prints the numbers the M2 plan requires: total time, failures, and per-card
character recall (how much of the ground-truth text the OCR actually read).
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent
CORPUS = ROOT / "corpus"
LOG = CORPUS / "ocr-log.jsonl"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def char_recall(ocr_text: str, gt_card: dict) -> float:
    """Share of ground-truth alphanumeric content that appears in the OCR output.

    Per GT field, the fraction of its words found in the OCR text; averaged over
    the fields present in the card.
    """
    ocr_words = set(normalize(ocr_text).split())
    scores = []
    for field in ("titulo", "autor", "data", "material", "dimensoes", "descricao"):
        value = gt_card.get(field)
        if not value:
            continue
        words = [w for w in normalize(value).split() if len(w) > 1]
        if not words:
            continue
        scores.append(sum(1 for w in words if w in ocr_words) / len(words))
    return sum(scores) / len(scores) if scores else 0.0


def main() -> int:
    entries = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    ok = [e for e in entries if e["status"] == "ok"]
    failed = [e for e in entries if e["status"] == "failed"]
    total_seconds = sum(e.get("seconds", 0) for e in ok)

    recalls = []
    empty = []
    for entry in ok:
        card_id = entry["card"]
        ocr = json.loads((CORPUS / "ocr" / f"{card_id}.json").read_text(encoding="utf-8"))
        gt = json.loads((CORPUS / "ground-truth" / f"{card_id}.json").read_text(encoding="utf-8"))
        if not ocr["text"].strip():
            empty.append(card_id)
        recalls.append(char_recall(ocr["text"], gt))

    recalls.sort()
    n = len(recalls)
    print(f"cards processed : {len(ok)} ok / {len(failed)} failed")
    print(f"engine time     : {total_seconds:.0f}s total, {total_seconds / max(len(ok), 1):.2f}s per card")
    print(f"char recall     : mean {sum(recalls) / n:.3f} | median {recalls[n // 2]:.3f} "
          f"| p10 {recalls[n // 10]:.3f} | min {recalls[0]:.3f}")
    print(f"empty OCR output: {len(empty)} card(s){': ' + ', '.join(empty[:5]) if empty else ''}")
    if failed:
        for entry in failed:
            print(f"  FAILED {entry['card']}: {entry['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

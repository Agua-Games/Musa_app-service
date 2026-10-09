"""Confidence report + review queue (M2.4): the X% number comes from here.

Crosses OCR output, structured cards and ground truth, per field:
  - OCR-pure accuracy:  was the ground-truth value readable in the raw OCR text?
  - post-LLM accuracy:  does the structured card field match the ground truth?
  - auto-approval rule: provenance in (ocr_read, llm_corrected) AND
    confidence >= threshold. llm_inferred ALWAYS goes to review (plan rule).
  - residual error:     among auto-approved fields, how many are wrong vs GT?

X% = share of fields auto-approved. The threshold curve (threshold × % auto ×
residual error) is what prices the service. tags are excluded from accuracy:
they are enrichment inferred by design, not transcription.

Usage:
    python confidence_report.py [--threshold 0.7]
Writes corpus/confidence-report.json and corpus/review-queue.json.
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
FIELDS = ("titulo", "autor", "data", "material", "dimensoes", "descricao")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def value_match(proposed: str, truth: str) -> float:
    """Token recall of the ground truth inside the proposed value (0..1)."""
    truth_words = [w for w in norm(truth).split() if len(w) > 1]
    if not truth_words:
        return 1.0 if not norm(proposed) else 0.0
    proposed_words = set(norm(proposed).split())
    return sum(1 for w in truth_words if w in proposed_words) / len(truth_words)


# Per-field comparators (documented, not gamed): the product question is
# "would a curator accept this value?", and each field answers it differently.
def compare(field: str, proposed: str, truth: str) -> bool:
    if field == "data":
        # Dates: the LLM is INSTRUCTED to normalize (AAAA, negative BCE), so
        # compare the content: GT year tokens and era markers must be preserved.
        truth_years = re.findall(r"\d{3,4}", truth)
        era_bce = bool(re.search(r"\b(b\.?c\.?e?\.?|a\.c\.)\b", norm(truth)))
        proposed_norm = norm(proposed)
        proposed_bce = bool(re.search(r"\b(b\.?c\.?e?\.?|a\.c\.)\b", proposed_norm)) \
            or str(proposed).strip().startswith("-")
        return all(y in str(proposed) for y in truth_years) and era_bce == proposed_bce
    if field == "dimensoes":
        # Dimensions: the numbers are the content; all GT numbers must survive.
        return all(n in str(proposed) for n in re.findall(r"\d+(?:[.,]\d+)?", truth))
    if field == "descricao":
        # Description: GT is terse ("Dish — Greek — Archaic"), the LLM writes a
        # factual sentence; content words (len >= 4) must be preserved.
        truth_words = [w for w in norm(truth).split() if len(w) >= 4]
        if not truth_words:
            return True
        proposed_words = set(norm(proposed).split())
        return sum(1 for w in truth_words if w in proposed_words) / len(truth_words) >= 0.5
    # titulo, autor, material: strict token recall.
    return value_match(proposed, truth) >= 0.8


COMPARATOR_RULES = {
    "titulo/autor/material": "recall de tokens do gabarito >= 0.8 (estrito)",
    "data": "anos e marcadores de era (a.C.) do gabarito preservados (LLM normaliza formato por instrução)",
    "dimensoes": "todos os números do gabarito presentes",
    "descricao": "recall de palavras de conteúdo (>=4 letras) >= 0.5 (gabarito é telegráfico, card é sentença)",
}


def evaluate(threshold: float) -> dict:
    rows = []
    for path in sorted((CORPUS / "structured").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["status"] != "ok":
            continue
        gt_path = CORPUS / "ground-truth" / path.name
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        ocr = json.loads((CORPUS / "ocr" / path.name).read_text(encoding="utf-8"))
        ocr_norm = norm(ocr["text"])
        for field in FIELDS:
            truth = gt.get(field)
            if not truth:
                continue  # field absent from GT: nothing to measure against
            proposed = record["card"].get(field, "")
            prov = (record["provenance"].get(field) or {})
            rows.append({
                "asset_id": record["asset_id"],
                "field": field,
                "proposed": proposed,
                "truth": truth,
                "source": prov.get("source", "missing"),
                "confidence": prov.get("confidence", 0.0),
                "ocr_could_read": value_match(" ".join(
                    w for w in norm(truth).split() if w in ocr_norm), truth) >= 1.0,
                "correct": compare(field, proposed, truth),
                "image": f"corpus/images/{record['asset_id']}.jpg",
            })
    for row in rows:
        row["auto_approved"] = (
            row["source"] in ("ocr_read", "llm_corrected")
            and row["confidence"] >= threshold
        )

    total = len(rows)
    auto = [r for r in rows if r["auto_approved"]]
    residual = [r for r in auto if not r["correct"]]
    report = {
        "comparator_rules": COMPARATOR_RULES,
        "threshold": threshold,
        "fields_measured": total,
        "auto_approved": len(auto),
        "x_percent_without_review": round(100 * len(auto) / total, 1) if total else 0.0,
        "residual_errors_in_auto": len(residual),
        "residual_error_rate": round(100 * len(residual) / len(auto), 2) if auto else 0.0,
        "ocr_pure_readability": round(100 * sum(r["ocr_could_read"] for r in rows) / total, 1),
        "post_llm_accuracy_all_fields": round(100 * sum(r["correct"] for r in rows) / total, 1),
        "by_field": {},
        "by_source": {},
    }
    for field in FIELDS:
        sub = [r for r in rows if r["field"] == field]
        if sub:
            report["by_field"][field] = {
                "n": len(sub),
                "post_llm_correct": round(100 * sum(r["correct"] for r in sub) / len(sub), 1),
                "auto_approved": round(100 * sum(r["auto_approved"] for r in sub) / len(sub), 1),
            }
    for source in ("ocr_read", "llm_corrected", "llm_inferred", "missing"):
        sub = [r for r in rows if r["source"] == source]
        if sub:
            report["by_source"][source] = {
                "n": len(sub),
                "correct": round(100 * sum(r["correct"] for r in sub) / len(sub), 1),
            }

    # Provenance-strict rule: the curve shows self-reported confidence is
    # uncalibrated (flat 0.0-0.8); the real signal is provenance. Rule B:
    # auto-approve ocr_read only.
    strict = [r for r in rows if r["source"] == "ocr_read"]
    strict_wrong = [r for r in strict if not r["correct"]]
    report["provenance_strict"] = {
        "rule": "auto-approve ocr_read only (llm_corrected e llm_inferred vão à fila)",
        "auto_percent": round(100 * len(strict) / total, 1),
        "residual_error": round(100 * len(strict_wrong) / len(strict), 2) if strict else 0.0,
    }

    curve = []
    for t in [x / 10 for x in range(0, 11)]:
        auto_t = [r for r in rows
                  if r["source"] in ("ocr_read", "llm_corrected") and r["confidence"] >= t]
        residual_t = [r for r in auto_t if not r["correct"]]
        curve.append({
            "threshold": t,
            "auto_percent": round(100 * len(auto_t) / total, 1),
            "residual_error": round(100 * len(residual_t) / len(auto_t), 2) if auto_t else 0.0,
        })
    report["threshold_curve"] = curve

    queue = [
        {k: r[k] for k in ("asset_id", "field", "proposed", "truth", "source", "confidence", "image")}
        for r in rows if not r["auto_approved"]
    ]
    return report, queue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.7)
    args = parser.parse_args()

    report, queue = evaluate(args.threshold)
    (CORPUS / "confidence-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (CORPUS / "review-queue.json").write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"fields measured : {report['fields_measured']}")
    print(f"X% sem revisão  : {report['x_percent_without_review']}% "
          f"(limiar {report['threshold']}, inferidos sempre revisados)")
    print(f"erro residual no auto-aprovado: {report['residual_error_rate']}%")
    print(f"OCR puro legível: {report['ocr_pure_readability']}% | "
          f"pós-LLM correto (todos os campos): {report['post_llm_accuracy_all_fields']}%")
    print("por campo:", json.dumps(report["by_field"], ensure_ascii=False))
    print("por proveniência:", json.dumps(report["by_source"], ensure_ascii=False))
    print(f"fila de revisão: {len(queue)} campo(s) em corpus/review-queue.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

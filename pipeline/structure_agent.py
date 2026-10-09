"""Structuring agent: OCR text -> contract-valid card.json with provenance (M2.3).

Per ADR 0012: output is validated IN CODE against the frozen contract v1 (the
builder's own validator); invalid output retries with the validation errors in
the prompt, max 2 retries, then the card goes to the review queue as a
structuring failure. Every field carries provenance (ocr_read / llm_corrected /
llm_inferred) — inferred fields ALWAYS go to review regardless of confidence.
Every paid call is logged with tokens and cost.

Usage (any python with `requests`; DeepSeek needs DEEPSEEK_API_KEY in the env):
    python structure_agent.py --provider mock --limit 5           # offline test
    python structure_agent.py --provider deepseek --offset 0 --limit 50
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "builder"))

from llm import make_provider  # noqa: E402
from musa_build.contract import make_validator, validate_card  # noqa: E402

OCR_DIR = ROOT / "corpus" / "ocr"
OUT_DIR = ROOT / "corpus" / "structured"
LOG = ROOT / "corpus" / "structure-log.jsonl"
MAX_RETRIES = 2
DOMAIN_CONTEXT = (ROOT / "domain_context.md").read_text(encoding="utf-8")

SYSTEM_PROMPT = """Você estrutura fichas de acervo de museu a partir de texto OCR, que pode conter erros de reconhecimento. Responda APENAS com JSON válido (sem markdown, sem comentários).

Formato JSON obrigatório:
{
  "card": {
    "titulo": "string",
    "autor": "string (omitir se ausente)",
    "data": "string (AAAA, AAAA-MM ou AAAA-MM-DD; datas a.C. como número negativo, ex.: -540)",
    "material": "string (omitir se ausente)",
    "dimensoes": "string (omitir se ausente)",
    "descricao": "string (omitir se ausente)",
    "tags": ["array de strings em português, minúsculas"]
  },
  "provenance": {
    "<campo>": {"source": "ocr_read|llm_corrected|llm_inferred", "confidence": 0.0-1.0}
  }
}

Regras:
1. ocr_read = o valor estava literalmente no texto; llm_corrected = erro óbvio de OCR corrigido; llm_inferred = não estava no texto (ex.: data completada por contexto histórico).
2. NUNCA invente autor ou material: se ausente ou ilegível, omita o campo.
3. Corrija apenas erros óbvios de OCR (ex.: "：‎" por ":", letras trocadas claras).
4. descricao: uma frase factual baseada só no texto lido."""

USER_TEMPLATE = """Texto OCR da ficha (pode conter erros):

{ocr_text}

Estruture como JSON conforme as regras."""

SYSTEM = SYSTEM_PROMPT + "\n\n" + DOMAIN_CONTEXT

BATCH_USER_TEMPLATE = """Abaixo estão {n} fichas, cada uma iniciada por "Nº <asset_id>". Estruture TODAS como JSON conforme as regras, no formato:

{{"items": [{{"asset_id": "<id exato da ficha>", "card": {{...}}, "provenance": {{...}}}}, ...]}}

Fichas:

{blocks}"""


def _finalize_card(card: dict, asset_id: str) -> dict:
    """Identity and batch-level fields never come from the LLM."""
    card = dict(card)
    card["asset_id"] = asset_id
    card["colecao"] = "acervo-importado"  # assigned at batch level (M2.6 target)
    card["website_status"] = "draft"  # nothing is born published
    card["tier"] = "bronze"
    return card


def structure_batch(records: list[dict], provider, validator) -> dict[str, dict]:
    """One request for N cards; each item validated individually (M2.3 batch mode).

    Returns {asset_id: result}. Items missing or invalid are NOT in the result —
    the caller falls back to individual calls for them.
    """
    blocks = "\n\n".join(f"Nº {r['asset_id']}\n{r['text'][:4000]}" for r in records)
    payload, usage = provider.complete_json(
        SYSTEM, BATCH_USER_TEMPLATE.format(n=len(records), blocks=blocks),
        max_tokens=max(2500, 600 * len(records)),
    )
    results: dict[str, dict] = {}
    for item in payload.get("items") or []:
        asset_id = item.get("asset_id")
        if asset_id not in {r["asset_id"] for r in records}:
            continue
        card = _finalize_card(dict(item.get("card") or {}), asset_id)
        errors = validate_card(card, validator)
        if not errors:
            results[asset_id] = {
                "asset_id": asset_id,
                "card": card,
                "provenance": item.get("provenance") or {},
                "retries": 0,
                "usage": {"batch": len(records), **usage},
                "status": "ok",
            }
    return results


def deterministic_id(titulo: str, salt: str) -> str:
    """asset_id from the title + a short hash of the source id; collisions fail."""
    import re
    import unicodedata

    slug = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")[:40] or "sem-titulo"
    digest = hashlib.sha1(salt.encode()).hexdigest()[:6]
    return f"{slug}-{digest}"


def log(entry: dict) -> None:
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def structure_one(ocr: dict, provider, validator) -> dict:
    """One OCR record -> structured result dict (card + provenance + usage)."""
    asset_id = ocr["asset_id"]
    user = USER_TEMPLATE.format(ocr_text=ocr["text"][:4000])
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
    errors: list[str] = []

    for attempt in range(MAX_RETRIES + 1):
        prompt = user
        if errors:
            prompt += "\n\nA resposta anterior falhou na validação do contrato:\n" + "\n".join(errors)
        payload, usage = provider.complete_json(SYSTEM, prompt)
        for key in usage_total:
            usage_total[key] += usage.get(key, 0) or 0

        card = _finalize_card(dict(payload.get("card") or {}), asset_id)
        provenance = payload.get("provenance") or {}

        errors = validate_card(card, validator)
        if not errors:
            return {
                "asset_id": asset_id,
                "card": card,
                "provenance": provenance,
                "retries": attempt,
                "usage": usage_total,
                "status": "ok",
            }
    return {"asset_id": asset_id, "status": "failed", "errors": errors, "usage": usage_total}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=1,
                        help="cards per request; >1 amortizes the system prompt, "
                             "per-item validation keeps isolation, failures fall back to solo calls")
    args = parser.parse_args()

    provider = make_provider(args.provider)
    validator = make_validator()
    ocr_files = sorted(OCR_DIR.glob("*.json"))
    batch = ocr_files[args.offset : (None if args.limit is None else args.offset + args.limit)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    done = failed = skipped = 0
    started = time.perf_counter()
    pending = []
    for path in batch:
        out = OUT_DIR / path.name
        if out.exists():
            skipped += 1
            continue
        pending.append(json.loads(path.read_text(encoding="utf-8")))

    for chunk_start in range(0, len(pending), args.batch_size):
        chunk = pending[chunk_start : chunk_start + args.batch_size]
        results: dict[str, dict] = {}
        if len(chunk) > 1:
            try:
                results = structure_batch(chunk, provider, validator)
                log({"batch": len(chunk), "ok": len(results),
                     "fallback": len(chunk) - len(results), "provider": args.provider})
            except Exception as exc:
                print(f"  batch of {len(chunk)} failed ({exc}) — falling back to solo calls", flush=True)
        for ocr in chunk:
            result = results.get(ocr["asset_id"])
            if result is None:  # solo path: batch disabled, or item fell back
                try:
                    result = structure_one(ocr, provider, validator)
                except Exception as exc:
                    result = {"asset_id": ocr["asset_id"], "status": "failed",
                              "errors": [f"{type(exc).__name__}: {exc}"]}
            if result["status"] == "ok":
                done += 1
                (OUT_DIR / f"{ocr['asset_id']}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            else:
                failed += 1
                (OUT_DIR / "failed").mkdir(exist_ok=True)
                (OUT_DIR / "failed" / f"{ocr['asset_id']}.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if ocr["asset_id"] not in results:  # solo calls already log inside the loop below
                log({**{k: result.get(k) for k in ("asset_id", "status", "retries", "usage")},
                     "errors": result.get("errors"), "provider": args.provider})
            print(f"  {result['status']} {result['asset_id']}", flush=True)

    total = round(time.perf_counter() - started, 1)
    print(f"STRUCTURE BATCH — {done} ok, {failed} failed, {skipped} skipped, {total}s wall")
    return 0


if __name__ == "__main__":
    sys.exit(main())

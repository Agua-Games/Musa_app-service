"""Validate every ground-truth card against the frozen contract v1 (M2.1).

The corpus is only useful if its ground truth passes the SAME validator the
builder uses — this script proves it, so a divergence between corpus and
contract is caught here, not inside the pipeline.

Usage:
    python validate_ground_truth.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
GT_DIR = ROOT / "corpus" / "ground-truth"

# Reuse the builder's validator — the gate is one, and it travels with the artifact.
sys.path.insert(0, str(ROOT.parent / "builder"))
from musa_build.contract import make_validator, validate_card  # noqa: E402


def main() -> int:
    if not GT_DIR.exists():
        print(f"no ground truth at {GT_DIR} — run render_corpus.py first", file=sys.stderr)
        return 1
    validator = make_validator()
    files = sorted(GT_DIR.glob("*.json"))
    failures = 0
    for path in files:
        card = json.loads(path.read_text(encoding="utf-8"))
        problems = validate_card(card, validator)
        for problem in problems:
            failures += 1
            print(f"INVALID {path.name}: {problem}")
    if failures:
        print(f"VALIDATION FAILED — {failures} problem(s) in {len(files)} card(s)")
        return 1
    print(f"VALIDATION OK — {len(files)} ground-truth card(s) pass contract v1")
    return 0


if __name__ == "__main__":
    sys.exit(main())

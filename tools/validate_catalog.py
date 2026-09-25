"""Validate the frontend catalog against the collection contract.

The contract (schemas/card.schema.json) is what makes "asset watertight"
verifiable rather than aspirational: see docs/adr/0001-camada-de-acervo.md.
This is the local equivalent of the build gate described in the technical spec,
section 6.2 -- a record that does not validate must not reach the site.

Usage:
    python tools/validate_catalog.py
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "card.schema.json"
CATALOG_PATH = ROOT / "source" / "data" / "catalog.json"


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    items = catalog.get("items", [])
    validator = Draft202012Validator(schema)

    failures = 0
    for item in items:
        errors = sorted(validator.iter_errors(item), key=lambda e: list(e.path))
        for error in errors:
            failures += 1
            location = "/".join(str(part) for part in error.path) or "<root>"
            print(f"FAIL {item.get('asset_id', '?')} :: {location} :: {error.message}")

    print(f"contract: {SCHEMA_PATH.relative_to(ROOT)}")
    print(f"catalog : {CATALOG_PATH.relative_to(ROOT)}")
    print(f"checked {len(items)} item(s), {failures} violation(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

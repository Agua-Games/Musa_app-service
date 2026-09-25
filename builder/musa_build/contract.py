"""Collection contract loading and card validation.

M0.5: the gate travels with the artifact. The schema bundled here is a copy of
``schemas/card.schema.json`` from the platform repository, kept in sync by
``tests/test_schema_sync.py`` — a client can never run a private version of
the gate (docs/HANDOFF.md §5.1).
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from . import CONTRACT_VERSION

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "card.schema.json"


def load_schema() -> dict:
    """Load the bundled contract, asserting it is the version this builder implements."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    version = schema.get("x-contract-version")
    if version != CONTRACT_VERSION:
        raise RuntimeError(
            f"bundled contract is version {version!r}, but this builder "
            f"implements {CONTRACT_VERSION!r} — rebuild the artifact"
        )
    return schema


def make_validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


def validate_card(card: dict, validator: Draft202012Validator) -> list[str]:
    """Return the list of contract violations for one card (empty = valid)."""
    problems = []
    for error in sorted(validator.iter_errors(card), key=lambda e: list(e.path)):
        location = "/".join(str(part) for part in error.path) or "<root>"
        problems.append(f"{location} :: {error.message}")
    return problems

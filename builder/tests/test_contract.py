"""The bundled schema must be the platform's schema — one source of truth."""

import json
import unittest
from pathlib import Path

from musa_build.contract import load_schema, make_validator, validate_ficha

PLATFORM_SCHEMA = (
    Path(__file__).resolve().parent.parent.parent / "schemas" / "ficha.schema.json"
)


class SchemaSyncTest(unittest.TestCase):
    def test_bundled_schema_matches_the_platform_schema(self):
        bundled = json.loads(load_schema.__globals__["SCHEMA_PATH"].read_text(encoding="utf-8"))
        platform = json.loads(PLATFORM_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(platform, bundled, "builder/musa_build/schemas drifted from schemas/")


class ContractTest(unittest.TestCase):
    def setUp(self):
        self.validator = make_validator()

    def test_load_schema_asserts_version(self):
        self.assertEqual(load_schema()["x-contract-version"], "1.0.0")

    def test_minimal_valid_ficha(self):
        ficha = {"asset_id": "a-1", "titulo": "Piece", "colecao": "gallery"}
        self.assertEqual(validate_ficha(ficha, self.validator), [])

    def test_missing_required_field_fails(self):
        ficha = {"asset_id": "a-1", "colecao": "gallery"}
        problems = validate_ficha(ficha, self.validator)
        self.assertTrue(any("titulo" in p for p in problems), problems)

    def test_available_model_requires_model_primary(self):
        ficha = {
            "asset_id": "a-1",
            "titulo": "Piece",
            "colecao": "gallery",
            "model_status": "available",
        }
        problems = validate_ficha(ficha, self.validator)
        self.assertTrue(any("model_primary" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()

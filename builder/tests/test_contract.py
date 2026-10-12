"""The bundled schema must be the platform's schema — one source of truth."""

import json
import unittest
from pathlib import Path

from musa_build import CONTRACT_VERSION
from musa_build.contract import load_schema, make_validator, validate_card

PLATFORM_SCHEMA = (
    Path(__file__).resolve().parent.parent.parent / "schemas" / "card.schema.json"
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
        self.assertEqual(load_schema()["x-contract-version"], CONTRACT_VERSION)

    def test_data_iso_pattern(self):
        """Contract 1.1.0: `data` is free text (museum reality); the optional
        `data_iso` companion is strictly patterned."""
        base = {"asset_id": "a-1", "titulo": "Piece", "colecao": "gallery"}
        self.assertEqual(validate_card({**base, "data": "late 16th century"}, self.validator), [])
        self.assertEqual(validate_card({**base, "data_iso": "1665"}, self.validator), [])
        self.assertEqual(validate_card({**base, "data_iso": "-500"}, self.validator), [])
        self.assertEqual(validate_card({**base, "data_iso": "1665-03"}, self.validator), [])
        self.assertTrue(validate_card({**base, "data_iso": "banana-com-ouro"}, self.validator))
        self.assertTrue(validate_card({**base, "data_iso": "1665-13"}, self.validator))

    def test_minimal_valid_card(self):
        card = {"asset_id": "a-1", "titulo": "Piece", "colecao": "gallery"}
        self.assertEqual(validate_card(card, self.validator), [])

    def test_missing_required_field_fails(self):
        card = {"asset_id": "a-1", "colecao": "gallery"}
        problems = validate_card(card, self.validator)
        self.assertTrue(any("titulo" in p for p in problems), problems)

    def test_available_model_requires_model_primary(self):
        card = {
            "asset_id": "a-1",
            "titulo": "Piece",
            "colecao": "gallery",
            "model_status": "available",
        }
        problems = validate_card(card, self.validator)
        self.assertTrue(any("model_primary" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()

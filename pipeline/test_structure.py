"""Unit tests for the structuring agent plumbing (M2.3) — MockProvider, no network.

Run with any python: python -m unittest test_structure -v
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "builder"))

import structure_agent  # noqa: E402
from llm import MockProvider  # noqa: E402
from musa_build.contract import make_validator  # noqa: E402

OCR_RECORD = {
    "asset_id": "met-999999",
    "engine": "docling",
    "seconds": 1.0,
    "text": "Título: Prato de maiólica\nData: ca. 1535-50\nMaterial: Maiolica",
    "blocks": [],
}


class StructureOneTest(unittest.TestCase):
    def setUp(self):
        self.validator = make_validator()

    def test_valid_card_with_provenance(self):
        result = structure_agent.structure_one(OCR_RECORD, MockProvider(), self.validator)
        self.assertEqual(result["status"], "ok")
        card = result["card"]
        self.assertEqual(card["titulo"], "Prato de maiólica")
        self.assertEqual(card["asset_id"], "met-999999")  # identity never from the LLM
        self.assertEqual(card["website_status"], "draft")  # nothing is born published
        self.assertEqual(card["colecao"], "acervo-importado")
        self.assertIn("titulo", result["provenance"])
        self.assertEqual(result["retries"], 0)
        problems = [p for p in structure_agent.validate_card(card, self.validator)]
        self.assertEqual(problems, [])

    def test_retry_then_success(self):
        result = structure_agent.structure_one(OCR_RECORD, MockProvider(fail_first=True), self.validator)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["retries"], 1)

    def test_missing_fields_omitted_not_invented(self):
        ocr = {**OCR_RECORD, "text": "Título: Vaso\n"}  # no author/material in the text
        result = structure_agent.structure_one(ocr, MockProvider(), self.validator)
        self.assertEqual(result["status"], "ok")
        self.assertNotIn("autor", result["card"])
        self.assertNotIn("material", result["card"])


if __name__ == "__main__":
    unittest.main()

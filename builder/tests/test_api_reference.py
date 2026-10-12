"""API reference freshness (M3.4 follow-up, owner request 2026-10-11).

The reference doc is GENERATED from the code (musa_build.api_reference),
never hand-edited. These tests are the enforcement: if an endpoint is added
without an annotation, generate() raises; if the committed doc is stale, the
diff test fails. Regenerate with:

    cd builder && python -m musa_build api-reference
"""

import unittest
from pathlib import Path

from musa_build import api_reference

DOC = Path(__file__).resolve().parent.parent.parent / "docs" / "api-reference.md"


class ApiReferenceTest(unittest.TestCase):
    def test_committed_doc_is_fresh(self):
        rendered = api_reference.generate()
        current = DOC.read_text(encoding="utf-8").replace("\r\n", "\n") if DOC.is_file() else ""
        self.assertEqual(
            current, rendered,
            f"{DOC} is stale — regenerate with `python -m musa_build api-reference`",
        )

    def test_every_discovered_endpoint_is_documented(self):
        # generate() raises when ANNOTATIONS and the routes diverge; reaching
        # the assertions below means the strict merge held.
        rendered = api_reference.generate()
        for method, path, _ in api_reference._discover_routes():
            self.assertIn(f"`{method} {path}`", rendered,
                          f"endpoint {method} {path} missing from the reference")

    def test_contract_fields_table_matches_the_schema(self):
        import json
        schema = json.loads(api_reference.SCHEMA_PATH.read_text(encoding="utf-8"))
        rendered = api_reference.generate()
        for field in schema["properties"]:
            self.assertIn(f"`{field}`", rendered,
                          f"contract field {field} missing from the reference")


if __name__ == "__main__":
    unittest.main()

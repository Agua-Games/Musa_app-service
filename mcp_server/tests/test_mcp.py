"""MUSA MCP server tests (M1.6): the toolbox over the fixture client, plus a
protocol smoke test — and the milestone's exit criterion: search results are
traceable to asset_ids."""

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "builder"))

from mcp_server.__main__ import Toolbox  # noqa: E402
from mcp_server.server import TOOL_SCHEMAS, make_handler, serve  # noqa: E402

CLIENT_OK = REPO_ROOT / "builder" / "tests" / "fixtures" / "client-ok"


class ToolboxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.toolbox = Toolbox(CLIENT_OK)

    def test_list_collections(self):
        result = self.toolbox.tools["list_collections"]()
        ids = {c["id"] for c in result["collections"]}
        self.assertEqual(ids, {"paintings", "sculptures"})
        self.assertEqual(result["entitled_tier"], "silver")
        for c in result["collections"]:
            self.assertTrue(c["source"].endswith("collection.json"))

    def test_get_item_cites_sources(self):
        result = self.toolbox.tools["get_item"](asset_id="painting-one")
        self.assertEqual(result["item"]["titulo"], "Painting One")
        self.assertTrue(result["published"])
        self.assertIn("asset_id:painting-one", result["sources"])
        self.assertTrue(any(s.endswith("ficha.json") for s in result["sources"]))

    def test_get_item_reports_the_gate(self):
        result = self.toolbox.tools["get_item"](asset_id="draft-one")
        self.assertFalse(result["published"])
        self.assertIn("website_status is 'draft'", result["reasons"][0])

    def test_get_item_unknown_is_an_error_with_a_hint(self):
        result = self.toolbox.tools["get_item"](asset_id="nope")
        self.assertIn("not found", result["error"])

    def test_search_results_are_traceable_to_asset_ids(self):
        # The M1.6 exit criterion.
        result = self.toolbox.tools["search"](query="statue")
        self.assertEqual(result["count"], 1)
        hit = result["results"][0]
        self.assertEqual(hit["asset_id"], "statue-one")
        self.assertIn("asset_id:statue-one", hit["sources"])
        self.assertTrue(any(s.endswith("statue-one/ficha.json") for s in hit["sources"]))

    def test_search_sees_drafts_the_site_never_serves(self):
        # The MCP is a dev/ops tool: it reads the repo (source of truth), not
        # the gated payload — drafts are findable here, never on the site.
        result = self.toolbox.tools["search"](query="draft")
        self.assertEqual({h["asset_id"] for h in result["results"]}, {"draft-one"})

    def test_validate_ficha(self):
        ok = self.toolbox.tools["validate_ficha"](ficha={
            "asset_id": "x", "titulo": "X", "colecao": "paintings"})
        self.assertTrue(ok["valid"])
        bad = self.toolbox.tools["validate_ficha"](ficha={"asset_id": "x"})
        self.assertFalse(bad["valid"])
        self.assertTrue(any("titulo" in p for p in bad["problems"]))

    def test_propose_correction_fixes_identity_and_flags_content(self):
        result = self.toolbox.tools["propose_ficha_correction"](
            ficha={"asset_id": "wrong", "colecao": "elsewhere"},
            folder="new-piece", collection="paintings",
        )
        self.assertEqual(result["corrected"]["asset_id"], "new-piece")
        self.assertEqual(result["corrected"]["colecao"], "paintings")
        self.assertEqual(result["corrected"]["website_status"], "draft")
        self.assertFalse(result["valid_after"])  # titulo missing — flagged, not invented
        self.assertTrue(any(c.startswith("NEEDS HUMAN INPUT") for c in result["changes"]))

    def test_upload_asset_is_an_honest_stub(self):
        result = self.toolbox.tools["upload_asset"](asset_id="x", path="y.glb")
        self.assertIn("M1.3", result["error"])

    def test_set_status_writes_the_ficha(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "client"
            shutil.copytree(CLIENT_OK, repo)
            toolbox = Toolbox(repo)
            result = toolbox.tools["set_status"](asset_id="draft-one", status="published")
            self.assertTrue(result["changed"])
            self.assertEqual(result["previous"], "draft")
            ficha = json.loads(
                (repo / "content" / "paintings" / "draft-one" / "ficha.json").read_text(encoding="utf-8"))
            self.assertEqual(ficha["website_status"], "published")
            # and back
            toolbox.tools["set_status"](asset_id="draft-one", status="draft")
            ficha = json.loads(
                (repo / "content" / "paintings" / "draft-one" / "ficha.json").read_text(encoding="utf-8"))
            self.assertEqual(ficha["website_status"], "draft")

    def test_build_report_runs_the_real_build(self):
        result = self.toolbox.tools["build_report"]()
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["counts"]["items_included"], 2)
        self.assertTrue(result["build_id"].startswith("b-"))


class ProtocolTest(unittest.TestCase):
    """The stdio JSON-RPC loop, fed with canned lines."""

    def run_session(self, *messages):
        toolbox = Toolbox(CLIENT_OK)
        stdin = io.StringIO("".join(json.dumps(m) + "\n" for m in messages))
        stdout = io.StringIO()
        serve(make_handler(toolbox), stdin=stdin, stdout=stdout)
        return [json.loads(l) for l in stdout.getvalue().splitlines()]

    def test_initialize_list_and_call(self):
        replies = self.run_session(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "search", "arguments": {"query": "statue"}}},
        )
        self.assertEqual(len(replies), 3)  # notifications get no reply
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "musa-mcp")
        tool_names = {t["name"] for t in replies[1]["result"]["tools"]}
        self.assertEqual(tool_names, {t["name"] for t in TOOL_SCHEMAS})
        payload = json.loads(replies[2]["result"]["content"][0]["text"])
        self.assertEqual(payload["results"][0]["asset_id"], "statue-one")

    def test_unknown_tool_is_a_jsonrpc_error(self):
        replies = self.run_session(
            {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
             "params": {"name": "nope", "arguments": {}}},
        )
        self.assertEqual(replies[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()

"""Structured-log tests (M1.5): a whole build must be reproducible from
build-log.jsonl alone — every gate decision and every emitted content file
appears as a JSON line with the tenant → build → asset correlation ids."""

import json
import tempfile
import unittest
from pathlib import Path

from musa_build.build import build_site

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
FRONTEND = FIXTURES / "frontend"

# Content files the log must account for (platform frontend files are one
# aggregated event; reports and the log itself are the run's metadata).
CONTENT_DIRS = ("data", "api", "assets/content")


class BuildLogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "site"
        cls.report = build_site(CLIENT_OK, FRONTEND, cls.out)
        cls.log_path = cls.out / "build-log.jsonl"
        cls.lines = [
            json.loads(line)
            for line in cls.log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def events(self, name):
        return [l for l in self.lines if l["event"] == name]

    def test_every_line_is_valid_json_with_correlation_ids(self):
        self.assertTrue(self.lines)
        for line in self.lines:
            self.assertEqual(line["tenant"], "fixture-museum")
            self.assertTrue(line["build"].startswith("b-"))
            self.assertIn("ts", line)
            self.assertIn("event", line)

    def test_build_id_matches_the_report(self):
        report_json = json.loads((self.out / "build-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report_json["build_id"], self.lines[0]["build"])

    def test_every_report_entry_has_a_gate_event(self):
        gate = {(l["asset"], l["included"]) for l in self.events("gate")}
        entries = {(e.ref, e.included) for e in self.report.entries}
        self.assertEqual(gate, entries)

    def test_every_emitted_content_file_is_logged(self):
        logged_paths = {l["path"] for l in self.events("file_emitted")}
        logged_paths |= {l["path"] for l in self.events("asset_write")}
        on_disk = {
            p.relative_to(self.out).as_posix()
            for d in CONTENT_DIRS
            for p in (self.out / d).rglob("*")
            if p.is_file()
        }
        self.assertTrue(on_disk)  # sanity: the fixture build emits content
        self.assertEqual(on_disk - logged_paths, set(),
                         "content files on disk with no log line — the build is not reproducible")

    def test_excluded_records_emit_nothing_and_the_log_says_why(self):
        report_json = json.loads((self.out / "build-report.json").read_text(encoding="utf-8"))
        by_ref = {e["ref"]: e for e in report_json["entries"]}
        self.assertEqual(by_ref["draft-one"]["artifacts"], [])
        self.assertIn("api/items/painting-one.json", by_ref["painting-one"]["artifacts"])
        draft_gate = [l for l in self.events("gate") if l.get("asset") == "draft-one"]
        self.assertEqual(len(draft_gate), 1)
        self.assertFalse(draft_gate[0]["included"])
        self.assertIn("website_status is 'draft'", draft_gate[0]["reasons"][0])

    def test_build_end_carries_the_counts(self):
        end = self.events("build_end")
        self.assertEqual(len(end), 1)
        self.assertEqual(end[0]["result"], "success")
        self.assertEqual(end[0]["items_included"], 2)
        self.assertGreaterEqual(end[0]["duration_ms"], 0)

    def test_markdown_report_shows_where_each_record_landed(self):
        md = (self.out / "build-report.md").read_text(encoding="utf-8")
        self.assertIn("emitted to", md)
        self.assertIn("`api/items/painting-one.json`", md)


class FailedBuildLogTest(unittest.TestCase):
    def test_a_failed_build_still_writes_the_log(self):
        import shutil

        from musa_build.build import BuildFailure

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "client"
            shutil.copytree(CLIENT_OK, repo)
            ficha = repo / "content" / "paintings" / "painting-one" / "ficha.json"
            data = json.loads(ficha.read_text(encoding="utf-8"))
            del data["titulo"]
            ficha.write_text(json.dumps(data), encoding="utf-8")
            out = Path(tmp) / "site"
            with self.assertRaises(BuildFailure) as ctx:
                build_site(repo, FRONTEND, out)
            ctx.exception.report.write(out)  # what the CLI does on failure
            lines = [
                json.loads(l)
                for l in (out / "build-log.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertTrue(any(l["event"] == "error" and "titulo" in l["message"] for l in lines))


if __name__ == "__main__":
    unittest.main()

"""M3.5 structural tests for the load harness (beta/load.py).

Not a benchmark — a small-scale proof that the generator, the build, the
serve and the report renderer work and stay deterministic. The real numbers
come from `python -m beta.load` and live in docs/M3_carga.md.
"""

import json
import tempfile
import unittest
from pathlib import Path

from beta import load


class SyntheticRepoTest(unittest.TestCase):
    def test_generation_is_deterministic_and_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            counts = load.make_synthetic_repo(repo, 120, seed=42)["collections"]
            self.assertEqual(sum(counts.values()), 120)
            cards = sorted(repo.glob("content/*/*/card.json"))
            self.assertEqual(len(cards), 120)

            # same seed, same asset_ids
            repo2 = Path(tmp) / "repo2"
            load.make_synthetic_repo(repo2, 120, seed=42)
            ids1 = [p.parent.name for p in cards]
            ids2 = [p.parent.name for p in sorted(repo2.glob("content/*/*/card.json"))]
            self.assertEqual(ids1, ids2)

            # every card validates against the platform contract
            from musa_build.contract import make_validator, validate_card
            validator = make_validator()
            for path in cards:
                card = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(validate_card(card, validator), [], path.parent.name)

            # no assets, no storage base — the build must never touch the network
            config = json.loads((repo / "museum.config.json").read_text(encoding="utf-8"))
            self.assertNotIn("storage", config)
            self.assertEqual(list(repo.glob("content/*/*/*.jpg")), [])

    def test_variants_beyond_the_seed_cache_stay_unique(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            n = 500  # seed cache holds 475 -> 25 cards are -v1 variants
            load.make_synthetic_repo(repo, n, seed=1)
            ids = [p.parent.name for p in repo.glob("content/*/*/card.json")]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(any(i.endswith("-v1") for i in ids))


class ScaleBenchmarkSmokeTest(unittest.TestCase):
    """One tiny end-to-end pass: build green, serve answers, latency shape."""

    def test_tiny_scale_runs_green(self):
        row = load.bench_item_scale(60, seed=42)
        self.assertEqual(row["items"], 60)
        self.assertGreater(row["build_s"], 0)
        self.assertGreater(row["payload_api_mb"], 0)
        for key in ("lat_items", "lat_search", "lat_item"):
            self.assertEqual({"p50", "p95", "max"}, set(row[key]))
            self.assertGreaterEqual(row[key]["p95"], row[key]["p50"])


class ReportRenderTest(unittest.TestCase):
    def test_report_marks_measured_vs_estimate(self):
        row = {"items": 500, "geracao_s": 0.1, "repo_mb": 1.0, "build_s": 1.0,
               "payload_api_mb": 0.9, "site_mb": 3.0, "serve_startup_ms": 100,
               "lat_items": {"p50": 1, "p95": 2, "max": 3},
               "lat_search": {"p50": 1, "p95": 2, "max": 3},
               "lat_item": {"p50": 1, "p95": 2, "max": 3}}
        doc = load.render_report([row], None, {"cpu": "x", "ram_gb": 1,
                                               "os": "y", "python": "3"},
                                 "test-run")
        self.assertIn("MEDIDO", doc)
        self.assertIn("ESTIMATIVA", doc)
        self.assertIn("| 500 |", doc)


if __name__ == "__main__":
    unittest.main()

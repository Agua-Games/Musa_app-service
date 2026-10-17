"""Static pages (content/paginas/*.md): build-time rendering into <slug>.html."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from musa_build.build import BuildFailure, build_site

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLIENT_OK = FIXTURES / "client-ok"
FRONTEND = FIXTURES / "frontend"

PRIVACIDADE = """---
titulo: Política de Privacidade
ordem: 1
---

# Política de Privacidade

Quase nada — **por desenho**. Sem contas, sem cookies.

## O que coletamos

- logs técnicos por 90 dias
- perguntas ao assistente, sem identificadores
"""

TERMOS = """---
titulo: Termos de Uso
ordem: 2
---

# Termos de Uso

Cada peça informa sua licença na própria ficha.
"""


def _client_with_pages(tmp: Path, pages: dict[str, str] | None) -> Path:
    """A copy of client-ok, optionally with content/paginas/*.md added."""
    repo = tmp / "repo"
    shutil.copytree(CLIENT_OK, repo)
    if pages is not None:
        paginas = repo / "content" / "paginas"
        paginas.mkdir()
        for name, text in pages.items():
            (paginas / name).write_text(text, encoding="utf-8")
    return repo


class PagesBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        repo = _client_with_pages(tmp, {"privacidade.md": PRIVACIDADE, "termos.md": TERMOS})
        cls.out = tmp / "site"
        cls.report = build_site(repo, FRONTEND, cls.out)
        cls.catalog = json.loads((cls.out / "data" / "catalog.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_pages_render_as_html_at_the_site_root(self):
        priv = (self.out / "privacidade.html").read_text(encoding="utf-8")
        self.assertIn("<h1>Política de Privacidade</h1>", priv)
        self.assertIn("<strong>por desenho</strong>", priv)
        self.assertIn("<h2>O que coletamos</h2>", priv)
        self.assertIn("<li>logs técnicos por 90 dias</li>", priv)
        self.assertTrue((self.out / "termos.html").is_file())

    def test_page_carries_museum_identity_and_a_relative_way_home(self):
        priv = (self.out / "privacidade.html").read_text(encoding="utf-8")
        self.assertIn("Política de Privacidade — Fixture Museum", priv)
        self.assertIn('href="index.html"', priv)  # relative: Pages hosts under a subpath

    def test_catalog_lists_pages_for_the_footer(self):
        self.assertEqual(
            [(p["slug"], p["titulo"]) for p in self.catalog["pages"]],
            [("privacidade", "Política de Privacidade"), ("termos", "Termos de Uso")],
        )

    def test_pages_are_public_regardless_of_tier(self):
        # the fixture museum is silver; pages are informational and never gated
        self.assertTrue(self.report.ok, self.report.errors)
        self.assertEqual(self.catalog["museum"]["tier"], "silver")
        self.assertEqual(len(self.catalog["pages"]), 2)


class PagesAbsentTest(unittest.TestCase):
    def test_no_pages_dir_means_an_empty_footer_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            report = build_site(CLIENT_OK, FRONTEND, out)
            self.assertTrue(report.ok, report.errors)
            catalog = json.loads((out / "data" / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(catalog["pages"], [])


class PagesValidationTest(unittest.TestCase):
    def _build_with(self, pages: dict[str, str]):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = _client_with_pages(Path(tmp.name), pages)
        try:
            return build_site(repo, FRONTEND, Path(tmp.name) / "site"), None
        except BuildFailure as exc:
            return None, exc.report

    def test_invalid_slug_fails_the_build(self):
        _, report = self._build_with({"Termos de Uso.md": TERMOS})
        self.assertIsNotNone(report)
        self.assertTrue(any("slug" in e for e in report.errors), report.errors)

    def test_missing_title_fails_the_build(self):
        _, report = self._build_with({"privacidade.md": "# Sem front matter com titulo\n\ncorpo\n"})
        self.assertIsNotNone(report)
        self.assertTrue(any("titulo" in e for e in report.errors), report.errors)

    def test_empty_body_fails_the_build(self):
        _, report = self._build_with({"privacidade.md": "---\ntitulo: Vazia\n---\n"})
        self.assertIsNotNone(report)
        self.assertTrue(any("corpo vazio" in e for e in report.errors), report.errors)

    def test_raw_html_in_the_markdown_is_escaped(self):
        evil = "---\ntitulo: Teste\n---\n\n# T\n\n<script>alert(1)</script>\n"
        with tempfile.TemporaryDirectory() as tmp:
            repo = _client_with_pages(Path(tmp), {"teste.md": evil})
            out = Path(tmp) / "site"
            report = build_site(repo, FRONTEND, out)
            self.assertTrue(report.ok, report.errors)
            rendered = (out / "teste.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>alert(1)</script>", rendered)
            self.assertIn("&lt;script&gt;", rendered)


if __name__ == "__main__":
    unittest.main()

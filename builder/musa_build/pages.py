"""Static pages (termos, privacidade, sobre) — client-owned markdown, rendered
into the site at build time.

A client repository MAY carry ``content/paginas/<slug>.md`` files:

    ---
    titulo: Política de Privacidade
    ordem: 1
    ---

    Corpo em **markdown**…

Each file becomes ``<slug>.html`` at the site root (GitHub Pages also serves
it at ``/<slug>``) and an entry in the catalog's ``pages`` list, which the
landing's footer turns into links. Pages are always public informational
content — they are NOT gated by tier or module, and they are not cards (the
collection contract does not apply).

Raw HTML inside the markdown is escaped (markdown-it default), so a client
page cannot inject scripts into the site.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from markdown_it import MarkdownIt

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
MAX_PAGE_BYTES = 256 * 1024  # a page is prose; bigger means a misplaced asset

# NOTE: markdown-it-py v4 quirk — MarkdownIt() no-arg enables html=True (raw
# markup passes through); the "default" preset does not. We pin html=False
# explicitly; test_raw_html_in_the_markdown_is_escaped guards this.
_md = MarkdownIt("default", {"html": False})

_TEMPLATE = """<!doctype html>
<html lang="{locale}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{titulo} — {museum}</title>
<meta name="description" content="{titulo} — {museum}" />
<link rel="stylesheet" href="assets/css/style.css" />
</head>
<body class="page-doc">
<header class="page-head wrap">
  <a class="page-home" href="index.html">← {museum}</a>
</header>
<main class="page-body wrap">
{body}
</main>
<footer class="page-foot wrap">
  <span>© {year} {museum}</span>
  <span>Publicado por MUSA · {generated}</span>
</footer>
</body>
</html>
"""


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Minimal ``---`` front matter: ``chave: valor`` lines, then the body."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:]).strip()
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return {}, text  # never closed: treat the whole file as body


def read_pages(repo: Path, report) -> list[dict]:
    """Read and validate content/paginas/*.md. Problems are build errors:
    a malformed page must fail loudly, never publish half-rendered."""
    pages_dir = repo / "content" / "paginas"
    if not pages_dir.is_dir():
        return []
    pages: list[dict] = []
    for path in sorted(pages_dir.glob("*.md")):
        slug = path.stem
        if not SLUG_RE.match(slug):
            report.fail(f"paginas/{path.name}: slug {slug!r} inválido — use a-z, 0-9 e '-'")
            continue
        if path.stat().st_size > MAX_PAGE_BYTES:
            report.fail(f"paginas/{path.name}: {path.stat().st_size} bytes — página grande "
                         f"demais (máx {MAX_PAGE_BYTES}); mídia pertence ao R2, não à página")
            continue
        meta, body = _parse_front_matter(path.read_text(encoding="utf-8"))
        titulo = meta.get("titulo", "").strip()
        if not titulo:
            report.fail(f"paginas/{path.name}: front matter sem 'titulo'")
            continue
        if not body:
            report.fail(f"paginas/{path.name}: corpo vazio")
            continue
        try:
            ordem = int(meta.get("ordem", "99"))
        except ValueError:
            report.fail(f"paginas/{path.name}: 'ordem' deve ser inteiro, veio {meta.get('ordem')!r}")
            continue
        pages.append({"slug": slug, "titulo": titulo, "ordem": ordem, "body": body})
    pages.sort(key=lambda p: (p["ordem"], p["slug"]))
    return pages


def emit_pages(pages: list[dict], museum_cfg: dict, generated: str, out: Path, log) -> list[dict]:
    """Render each page to <slug>.html; return the catalog footer entries."""
    emitted = []
    year = generated[:4]
    for page in pages:
        body_html = _md.render(page["body"])
        doc = _TEMPLATE.format(
            locale=html.escape(museum_cfg.get("locale", "pt-BR")),
            titulo=html.escape(page["titulo"]),
            museum=html.escape(museum_cfg.get("name", "")),
            body=body_html,
            year=year,
            generated=generated,
        )
        target = out / f"{page['slug']}.html"
        target.write_text(doc, encoding="utf-8")
        log.log("file_emitted", path=target.name, bytes=len(doc))
        emitted.append({"slug": page["slug"], "titulo": page["titulo"], "ordem": page["ordem"]})
    return emitted

"""Fail the build on frontend mistakes that only surface in a browser.

This project has no browser test runner, and both checks below cover failures
that are SILENT: the page looks healthy and one whole feature is simply dead.

1. Import map entries whose value is not URL-like. The import-map parser
   normalises such an entry to `null`, and a matching null entry terminates
   resolution with no fallback: every `import ... from "three"` then dies with

       Resolution of specifier "three" was blocked by a null entry.

   That is exactly how both WebGL viewers were dead on 2026-09-18 while every
   file was present, reachable and 200 OK -- the map said
   "assets/vendor/three/three.module.js" (a BARE specifier) instead of
   "./assets/vendor/three/three.module.js". See docs/HANDOFF.md section 7.

2. A mapped target that is not in the tree at all (a vendored bundle that was
   never fetched, an asset renamed out from under the map).

Usage:
    python tools/check_frontend.py      # exit 0 = clean, 1 = violations
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "source")
INDEX = os.path.join(SITE, "index.html")

SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")
MAP_RE = re.compile(
    r'<script\s+type="importmap"\s*>(?P<body>.*?)</script>', re.DOTALL
)


def url_like(value: str) -> bool:
    """True when a specifier map value is a legal import-map address."""
    return value.startswith("/") or value.startswith("./") or value.startswith("../") or bool(SCHEME.match(value))


def local_target(value: str):
    """Path under the site root for a document-relative map value, else None."""
    if not (value.startswith("./") or value.startswith("/")):
        return None
    return os.path.normpath(os.path.join(SITE, value.lstrip("./")))


def check_import_map(html: str):
    problems = []
    found = MAP_RE.search(html)
    if not found:
        return problems, 0

    try:
        data = json.loads(found.group("body"))
    except json.JSONDecodeError as exc:
        return [f"import map is not valid JSON: {exc}"], 0

    checked = 0
    for section in ("imports", "scopes"):
        block = data.get(section)
        if not isinstance(block, dict):
            continue
        entries = block.values() if section == "scopes" else [block]
        for group in entries:
            if not isinstance(group, dict):
                continue
            for key, value in group.items():
                checked += 1
                if not isinstance(value, str):
                    problems.append(f'{section}["{key}"] is not a string ({value!r})')
                    continue
                if not url_like(value):
                    problems.append(
                        f'{section}["{key}"] = "{value}" is a BARE specifier; '
                        f'the entry is normalised to null and resolution FAILS with no fallback. '
                        f'Use "./{value.lstrip("./")}"'
                    )
                    continue
                if key.endswith("/") != value.endswith("/"):
                    problems.append(
                        f'{section}["{key}"] must agree with "{value}" on the trailing slash'
                    )
                    continue
                target = local_target(value)
                if target and not os.path.exists(target):
                    problems.append(
                        f'{section}["{key}"] points at "{value}" but {os.path.relpath(target, ROOT)} is not here'
                    )
    return problems, checked


def main() -> int:
    if not os.path.exists(INDEX):
        print(f"FAIL  {os.path.relpath(INDEX, ROOT)} is missing")
        return 1

    with open(INDEX, encoding="utf-8") as handle:
        html = handle.read()

    problems, checked = check_import_map(html)

    if problems:
        print(f"FAIL  frontend checks ({len(problems)} violation(s)):")
        for item in problems:
            print(f"  - {item}")
        return 1

    print(f"ok    import map: {checked} entr(y|ies) URL-like and resolvable")
    return 0


if __name__ == "__main__":
    sys.exit(main())

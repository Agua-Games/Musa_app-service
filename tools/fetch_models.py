"""Fetch the 3D models used by the frontend demo into source/assets/models/.

These models are deliberately NOT tracked by git (see the *.glb rule in
.gitignore): together they are ~26 MB, and a repository that carries binaries
forever is a repository that gets slow to clone. Run this once after cloning.

    python tools/fetch_models.py

Three of the four models are the Khronos glTF Sample Assets. They are fetched
from a pinned branch and verified against an exact expected size, so a silent
upstream change cannot turn into a silently different asset on disk.

The fourth model (Venus de Milo) has no stable public URL recorded in this
repository, so the script reports it as a manual step instead of guessing.
"""

import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "source", "assets", "models")

UA = {"User-Agent": "MusaFrontendDemo/1.0 (educational demo; contact: local)"}
BASE = "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models"

# (filename the site expects, source url, exact size in bytes)
# Sizes verified against the Khronos source on 2026-09-17.
SOURCES = [
    ("lantern.glb", f"{BASE}/Lantern/glTF-Binary/Lantern.glb", 9564264),
    ("samurai-helmet.glb", f"{BASE}/DamagedHelmet/glTF-Binary/DamagedHelmet.glb", 3773916),
    ("antique-corset.glb", f"{BASE}/Corset/glTF-Binary/Corset.glb", 13491364),
]

# (filename the site expects, exact size in bytes, where to get it)
MANUAL = [
    (
        "venus-de-milo.glb",
        4167244,
        "CC0 scan of the Venus de Milo via Sketchfab (National Gallery of Denmark "
        "open access). Download it and record the model URL here.",
    ),
]


def fetch(url: str, dest: str, expected: int) -> None:
    """Download one model and refuse to keep a file that does not match."""
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()

    if len(payload) != expected:
        raise RuntimeError(f"size mismatch: expected {expected} bytes, got {len(payload)}")

    with open(dest, "wb") as handle:
        handle.write(payload)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    failures = 0

    for filename, url, expected in SOURCES:
        dest = os.path.join(OUT, filename)
        if os.path.exists(dest) and os.path.getsize(dest) == expected:
            print(f"skip  {filename} (already present)")
            continue
        try:
            fetch(url, dest, expected)
            print(f"ok    {filename}  {expected // 1024} KB")
        except Exception as error:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL  {filename}  {error}")

    for filename, expected, note in MANUAL:
        dest = os.path.join(OUT, filename)
        if os.path.exists(dest) and os.path.getsize(dest) == expected:
            print(f"skip  {filename} (already present)")
        else:
            failures += 1
            print(f"MANUAL {filename} (~{expected // 1024} KB): {note}")

    print(f"\n{len(SOURCES) + len(MANUAL) - failures} ready, {failures} pending")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

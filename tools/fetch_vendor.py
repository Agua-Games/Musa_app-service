"""Vendor three.js into source/assets/vendor/ (browser ES modules, no bundler).

The frontend loads three.js through an import map (see source/index.html). The
CDN is deliberately NOT used at runtime: a venue or kiosk may sit behind a
network that blocks third-party CDNs, and a blocked import silently disables the
whole 3D viewer. Vendoring the exact pinned revision keeps the site self-hosted.

Usage:
    python tools/fetch_vendor.py

It writes the layout the import map expects:

    source/assets/vendor/three/three.module.js
    source/assets/vendor/three/addons/controls/OrbitControls.js
    source/assets/vendor/three/addons/environments/RoomEnvironment.js
    source/assets/vendor/three/addons/loaders/GLTFLoader.js
    source/assets/vendor/three/addons/utils/BufferGeometryUtils.js

Like tools/fetch_models.py, these files are reproducible build inputs rather
than hand-edited source; keep them out of git and re-run this script instead
(see docs/adr/0004-frontend-auto-hospedado.md).
"""
import os
import sys
import urllib.request

THREE_VERSION = "0.160.0"
BASE = f"https://cdn.jsdelivr.net/npm/three@{THREE_VERSION}/"
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "source", "assets", "vendor", "three",
)

# destination (inside OUT) -> upstream path (relative to BASE)
FILES = {
    "three.module.js": "build/three.module.js",
    "addons/controls/OrbitControls.js": "examples/jsm/controls/OrbitControls.js",
    "addons/environments/RoomEnvironment.js": "examples/jsm/environments/RoomEnvironment.js",
    "addons/loaders/GLTFLoader.js": "examples/jsm/loaders/GLTFLoader.js",
    "addons/utils/BufferGeometryUtils.js": "examples/jsm/utils/BufferGeometryUtils.js",
}

UA = {"User-Agent": "MusaFrontendDemo/1.0 (three.js vendoring; educational demo)"}


def main() -> int:
    failed = []
    for dest_rel, src_rel in FILES.items():
        dest = os.path.join(OUT, dest_rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            req = urllib.request.Request(BASE + src_rel, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"ok   {dest_rel} {len(data) // 1024} KB")
        except Exception as e:  # report and keep going; exit non-zero at the end
            failed.append(dest_rel)
            print(f"FAIL {dest_rel}: {e}")

    total = len(FILES)
    print(f"\nthree.js r{THREE_VERSION.split('.')[1]} — {total - len(failed)}/{total} files")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

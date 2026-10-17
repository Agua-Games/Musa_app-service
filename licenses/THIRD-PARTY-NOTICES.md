# Third-Party Notices

MUSA incorporates the following third-party open-source components. Each
remains the property of its respective authors and is used under the license
indicated. Canonical license texts live in this directory; where a component
is vendored into the repository, its copyright header is also preserved in
the vendored file itself.

## Frontend (vendored, shipped to client sites)

| Component | Version | License | Copyright |
|---|---|---|---|
| three.js | r160 (vendored in `source/assets/vendor/three/`) | [MIT](./MIT.txt) | © 2010–2023 Three.js Authors |
| RoomEnvironment (three.js addon, derived from Google `<model-viewer>`) | r160 subset | [Apache-2.0](./Apache-2.0.txt) | © Google LLC |

## Builder / app (Python — `builder/pyproject.toml`)

| Component | License |
|---|---|
| jsonschema | [MIT](./MIT.txt) |
| cryptography | [Apache-2.0](./Apache-2.0.txt) OR [BSD-3-Clause](./BSD-3-Clause.txt) |
| FastAPI | [MIT](./MIT.txt) |
| Uvicorn | [BSD-3-Clause](./BSD-3-Clause.txt) |
| httpx | [BSD-3-Clause](./BSD-3-Clause.txt) |
| boto3 | [Apache-2.0](./Apache-2.0.txt) |
| markdown-it-py | [MIT](./MIT.txt) |

## OCR / AI pipeline (Python — `pipeline/requirements-ocr.txt`)

| Component | License |
|---|---|
| docling, docling-core, docling-parse, docling-slim | [MIT](./MIT.txt) |
| docling-ibm-models | [Apache-2.0](./Apache-2.0.txt) / CDLA (model weights) |
| RapidOCR (rapidocr, rapidocr-onnxruntime) | [Apache-2.0](./Apache-2.0.txt) |
| ONNX Runtime | [MIT](./MIT.txt) |
| PyTorch / torchvision | [BSD-3-Clause](./BSD-3-Clause.txt) |
| NumPy | [BSD-3-Clause](./BSD-3-Clause.txt) |
| Hugging Face `huggingface_hub` / `tokenizers` | [Apache-2.0](./Apache-2.0.txt) |
| sqlite-vec | [MIT](./MIT.txt) |

## Data storage

| Component | License |
|---|---|
| SQLite (database engine, via Python stdlib `sqlite3`) | Public domain — see [SQLite.md](./SQLite.md) |

## Notes

- License texts are canonical copies; authoritative sources:
  MIT <https://opensource.org/license/mit>, Apache-2.0
  <https://www.apache.org/licenses/LICENSE-2.0.txt>, BSD-3-Clause
  <https://opensource.org/license/bsd-3-clause>, SQLite
  <https://www.sqlite.org/copyright.html>.
- If a dependency is added or upgraded, add/update its row here and keep the
  license file in this directory.
- Fonts loaded at runtime (Cormorant Garamond, Inter — Google Fonts) are
  licensed under the SIL Open Font License 1.1 and are fetched, not vendored.

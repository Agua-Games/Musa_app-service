# MUSA — Website / Frontend (milestone scaffold)

The service frontend for **MUSA**, the app-service for museums, galleries, art
cinema rooms, bookstores and other venues with collections. Static, dependency
free at runtime except CDN fonts/Three.js, and shaped to plug into the backend
milestones without view-layer changes.

## Run

```bash
npm run dev                 # http://0.0.0.0:7100/
npm run dev -- --port 8080  # CLI args are forwarded
```

or simply serve this folder with any static server and open `index.html`.

## What's inside (single scrolling page)

| Section | Tier | Notes |
|---|---|---|
| Hero + AI assistant field | — | Translucent glass ask-box wired to `MusaAPI.assistantAsk` (mock RAG answers until `/assistant/ask` exists) |
| Collections overview | — | Cards generated from the API layer |
| The Room (clickable gallery wall) | any | High-aesthetic gallery photograph as backdrop; pulsing hotspot markers (`wallHotspots` in the catalog, percent coordinates) open an elegant popup frame — large artwork, caption/ficha, prev/next for multi-piece areas, and a direct handoff to the 3D viewer for modeled pieces |
| Old Masters photo gallery | Bronze | Masonry grid, lightbox with zoom/pan/maximize |
| Interactive 3D gallery | Silver | Grid with label overlays; cards open a WebGL viewer (local GLB: Venus de Milo scan from SMK/Sketchfab CC0, corset, kabuto). `kit_stream` records render a streaming placeholder; `processing` records show pipeline status |
| Digital twin "Room A" | Gold | Procedural WebGL twin: parquet floor, framed works as textures, pedestal sculptures, track lighting, click-to-inspect |
| Screening room | module | Video player scaffold (quality ladder, CC, fullscreen) + playlist/schedule; demo sample streams |
| Store | module | Product grid + cart drawer scaffold, template for the commerce module |
| Plans | — | Bronze/Silver/Gold tiers + module add-ons with a live price estimator (BRL, from the design doc) |
| Sign-in & admin | — | Two admin tiers (demo: `owner@musa.demo` / `team@musa.demo`, password `demo`): venue owner gets a folder-style collection browser (checkboxes, publish/demote, hero promotion, per-item visibility); MUSA team gets an ops console. Tier switch enforces credentials |

## Backend readiness

All data access goes through **`assets/js/api.js` (`MusaAPI`)**, which mirrors
the REST contract from `docs/Musa_design document_technical-specs_v1.1.md`:

| Frontend call | REST target |
|---|---|
| `listCollections()` | `GET /collections` |
| `listItems(id)` | `GET /collections/{id}/items` |
| `getItem(id)` | `GET /items/{id}` |
| `search(q)` | `GET /search?q=` |
| `saveItem(patch)` | `POST /items` |
| `assistantAsk(q)` | `POST /assistant/ask` |
| `login()` | `POST /auth/login` (JWT) |

Today `MusaAPI` runs in `mock` mode over `data/catalog.js` (records shaped
after `schemas/ficha.schema.json`, plus website-presentation fields). Switch to
live with:

```js
MusaAPI.configure({ mode: "live", baseUrl: "https://api.musa.example/v1", token: "<JWT>" });
```

Records declare their viewer via `model_viewer` (`three_js` | `kit_stream`) and
delivery asset via `model_primary`, per ADR-0001 — the views never hard-code a
viewer choice.

## Assets & licensing

All imagery is public-domain / open-license material downloaded from
**Wikimedia Commons** (`tools/fetch_assets.py` reproduces the set). 3D models:
Venus de Milo scan (CC0, National Gallery of Denmark via Sketchfab cultural
heritage), Corset / Lantern / DamagedHelmet (Khronos glTF sample assets).
Demo video streams are public Google sample videos.

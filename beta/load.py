"""M3.5 load harness: N museums × M items, measured locally.

Synthetic client repositories are generated from the Met seed cache
(pipeline/corpus/seed/met-objects.json) using the same card shape as the M2
corpus (render_corpus.ground_truth) — METADATA ONLY: no images, no assets,
no `storage.assetsBaseUrl` in the config, so builds never touch the network
(check_remote_assets returns immediately) and nothing reaches Cloudflare/R2.

Two benchmark families:
  1. Item scale per museum — build time, emitted payload size, serve startup,
     and latency of /collections/{id}/items, /search and /items/{id} at
     500 / 2.000 / 5.000 / 10.000 cards.
  2. Museum scale — N serve instances in one process (port isolation),
     memory per instance (marginal RSS) and latency under sequential load.

Raw results land in beta/out/load-<run>.json; the curated report is rendered
to docs/M3_carga.md. Every number in the report is marked MEDIDO (measured
on this machine) or ESTIMATIVA (formula/extrapolation/published pricing).

Usage:
    python -m beta.load                      # full run, writes docs/M3_carga.md
    python -m beta.load --scales 500,2000    # partial
    python -m beta.load --skip-museums       # only item scale
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import beta  # noqa: F401  (puts builder/ on sys.path)
from beta.client import ApiClient

PLATFORM_ROOT = Path(__file__).resolve().parent.parent
BUILDER_DIR = PLATFORM_ROOT / "builder"
FRONTEND_DIR = PLATFORM_ROOT / "source"
PIPELINE_DIR = PLATFORM_ROOT / "pipeline"
SEED_CACHE = PIPELINE_DIR / "corpus" / "seed" / "met-objects.json"
DEFAULT_DOC = PLATFORM_ROOT / "docs" / "M3_carga.md"
RAW_DIR = PLATFORM_ROOT / "beta" / "out"

sys.path.insert(0, str(PIPELINE_DIR))
from render_corpus import ground_truth  # noqa: E402  (M2 card shape reuse)

TOKEN = "load-test-token"
LATENCY_REQUESTS = 30


# ---------------------------------------------------------------------------
# synthetic repository generation (metadata only, deterministic)
# ---------------------------------------------------------------------------

def _load_seed_objects() -> list[dict]:
    objects = list(json.loads(SEED_CACHE.read_text(encoding="utf-8")).values())
    return [o for o in objects if o.get("title", "").strip()]


def make_synthetic_repo(dest: Path, n_items: int, seed: int = 42) -> dict:
    """Write a client repo with n_items cards (no assets) under dest.

    Cards cycle the 475 Met seed objects; beyond that, deterministic variants
    (met-<id>-v<k>) keep asset_ids unique and descriptions distinguishable.
    Returns {"collections": {id: count}}.
    """
    objects = _load_seed_objects()
    rng = random.Random(seed)
    dest.mkdir(parents=True, exist_ok=True)

    config = {
        "museum": {
            "id": f"load-{n_items}",
            "name": f"Load Test Museum ({n_items})",
            "tagline": "Synthetic load corpus",
            "locale": "pt-BR",
            "domain": "load.musa.example",
        },
        # dev marker: unsigned entitlements are accepted in development builds
        "musa": "0.0.0-unreleased",
        # gold tier: every card is included, isolating pure scale effects
        "entitlements": {"tier": "gold", "modules": ["assistant", "store"],
                         "issued": "2026-10-12", "signature": None},
        # no storage.assetsBaseUrl -> the build never checks remote assets
    }
    (dest / "museum.config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    titles = {
        "asian-art": "Asian Art",
        "greek-roman-art": "Greek and Roman Art",
        "european-decorative-arts": "European Sculpture and Decorative Arts",
        "egyptian-art": "Egyptian Art",
        "european-paintings": "European Paintings",
    }
    for i in range(n_items):
        base = objects[i % len(objects)]
        variant = i // len(objects)
        card = ground_truth(base)
        if variant:
            card["asset_id"] = f"{card['asset_id']}-v{variant}"
            card["descricao"] = (card.get("descricao") or "") + f" — variante {variant}"
        col = card["colecao"]
        item_dir = dest / "content" / col / card["asset_id"]
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "card.json").write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts[col] = counts.get(col, 0) + 1

    for col in counts:
        meta = {"title": titles.get(col, col), "description": "Synthetic load collection",
                "tier": "bronze"}
        (dest / "content" / col / "collection.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _ = rng  # reserved for future jitter; generation is already deterministic
    return {"collections": counts}


# ---------------------------------------------------------------------------
# measurement helpers
# ---------------------------------------------------------------------------

def _rss_bytes() -> int:
    """Current process working set (Windows) / max RSS (POSIX)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        # restype/argtypes as HANDLE: the current-process pseudo-handle is a
        # 64-bit -1; the ctypes default truncates it to 32 bits and the call
        # fails with ERROR_INVALID_HANDLE.
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        get_info = kernel32.K32GetProcessMemoryInfo
        get_info.restype = wintypes.BOOL
        get_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
        counters = _PMC()
        counters.cb = ctypes.sizeof(_PMC)
        get_info(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return int(counters.WorkingSetSize)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024


def _machine_info() -> dict:
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpu": os.environ.get("PROCESSOR_IDENTIFIER", platform.processor() or "?"),
    }
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class _MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                        ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                        ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                        ("ullAvailExtendedVirtual", ctypes.c_uint64)]

        stat = _MEMSTAT()
        stat.dwLength = ctypes.sizeof(_MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
        info["ram_gb"] = round(stat.ullTotalPhys / 1e9, 1)
    return info


def _dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _percentiles(samples: list[float]) -> dict:
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return {"p50": round(statistics.median(ordered), 1),
            "p95": round(p95, 1),
            "max": round(ordered[-1], 1)}


def _time_build(repo: Path, out: Path) -> tuple[float, int]:
    """Real subprocess build, exactly like the CI runs it. Returns (s, exit)."""
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "musa_build", "build",
         "--repo", str(repo), "--frontend", str(FRONTEND_DIR), "--out", str(out)],
        cwd=str(BUILDER_DIR), capture_output=True, text=True, timeout=1800,
    )
    elapsed = time.monotonic() - t0
    if proc.returncode != 0:
        tail = ((proc.stdout or "") + (proc.stderr or ""))[-500:]
        raise RuntimeError(f"build failed for {repo}: {tail}")
    return elapsed, proc.returncode


class ServeInstance:
    """In-thread uvicorn server against a disposable overlay (test_beta pattern)."""

    def __init__(self, repo: Path, data_dir: Path):
        import uvicorn
        from musa_build.serve import create_app

        self.app = create_app(repo, data_dir=data_dir)
        import socket
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.server = uvicorn.Server(
            uvicorn.Config(self.app, host="127.0.0.1", port=self.port, log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.client = ApiClient(f"http://127.0.0.1:{self.port}")

    def start(self) -> float:
        """Boot and wait for /health. Returns startup time in ms."""
        t0 = time.monotonic()
        self.thread.start()
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                if self.client.health(timeout=1.5).ok:
                    return (time.monotonic() - t0) * 1000
            except Exception:
                time.sleep(0.15)
        raise RuntimeError(f"serve did not come up on port {self.port}")

    def latency(self, kind: str, target: str, n: int = LATENCY_REQUESTS) -> dict:
        samples = []
        for _ in range(n):
            t0 = time.monotonic()
            if kind == "items":
                res = self.client.collection_items(target)
            elif kind == "search":
                res = self.client.search(target)
            else:
                res = self.client.item(target)
            samples.append((time.monotonic() - t0) * 1000)
            assert res.ok, f"{kind} {target}: {res.status}"
        return _percentiles(samples)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=15)
        self.app.state.serve.store.close()


def _rmtree_retry(path: Path) -> None:
    """Windows keeps the overlay SQLite locked for a few hundred ms."""
    for _ in range(10):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(0.5)
    shutil.rmtree(path, ignore_errors=True)


# ---------------------------------------------------------------------------
# benchmark 1: item scale per museum
# ---------------------------------------------------------------------------

def bench_item_scale(n_items: int, seed: int = 42) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix=f"musa-load-{n_items}-"))
    try:
        repo = tmp / "repo"
        t0 = time.monotonic()
        counts = make_synthetic_repo(repo, n_items, seed)["collections"]
        gen_s = time.monotonic() - t0
        repo_mb = _dir_size(repo) / 1e6

        build_s, _ = _time_build(repo, tmp / "site")
        payload_mb = _dir_size(tmp / "site" / "api") / 1e6
        site_mb = _dir_size(tmp / "site") / 1e6

        inst = ServeInstance(repo, tmp / "overlay")
        try:
            startup_ms = inst.start()
            largest = max(counts, key=counts.get)
            first_card = sorted((repo / "content" / largest).glob("*/card.json"))[0]
            first_id = json.loads(first_card.read_text(encoding="utf-8"))["asset_id"]
            lat_items = inst.latency("items", largest)
            lat_search = inst.latency("search", "art")
            lat_item = inst.latency("item", first_id)
        finally:
            inst.stop()
        return {
            "items": n_items,
            "geracao_s": round(gen_s, 1),
            "repo_mb": round(repo_mb, 2),
            "build_s": round(build_s, 1),
            "payload_api_mb": round(payload_mb, 2),
            "site_mb": round(site_mb, 2),
            "serve_startup_ms": round(startup_ms),
            "lat_items": lat_items,
            "lat_search": lat_search,
            "lat_item": lat_item,
        }
    finally:
        _rmtree_retry(tmp)


# ---------------------------------------------------------------------------
# benchmark 2: museum scale (N instances, one process)
# ---------------------------------------------------------------------------

def bench_museum_scale(counts: list[int], items_per: int, seed: int = 42) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="musa-load-museums-"))
    instances: list[ServeInstance] = []
    rows = []
    try:
        repos = []
        for i in range(max(counts)):
            repo = tmp / f"repo-{i}"
            make_synthetic_repo(repo, items_per, seed + i)
            repos.append(repo)

        gc.collect()
        time.sleep(1)
        baseline = _rss_bytes()
        prev = baseline
        for n in counts:
            while len(instances) < n:
                inst = ServeInstance(repos[len(instances)],
                                     tmp / f"overlay-{len(instances)}")
                inst.start()
                instances.append(inst)
            gc.collect()
            time.sleep(1)
            rss = _rss_bytes()
            # sequential probe: 10 item-list requests per instance
            probes = [inst.latency("items", "asian-art", n=10)["p50"]
                      for inst in instances]
            rows.append({
                "instances": n,
                "rss_mb": round(rss / 1e6, 1),
                "marginal_mb_por_instancia": round((rss - prev) / 1e6 /
                                                   (n - (rows[-1]["instances"] if rows else 0)), 1),
                "lat_items_p50_ms": round(statistics.median(probes), 1),
            })
            prev = rss
        return {"items_por_museu": items_per,
                "rss_base_mb": round(baseline / 1e6, 1),
                "rows": rows}
    finally:
        for inst in instances:
            inst.stop()
        _rmtree_retry(tmp)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def render_report(scales: list[dict], museums: dict | None,
                  machine: dict, run_id: str) -> str:
    add = []
    a = add.append
    a("# M3.5 — Carga: N museus × M itens")
    a("")
    a(f"> Medição local de {run_id} (máquina do estúdio: {machine.get('cpu', '?')}, "
      f"{machine.get('ram_gb', '?')} GB RAM, {machine.get('os', '?')}, Python {machine.get('python', '?')}). "
      "Corpus sintético **só de metadados** (cards JSON do seed do Met, sem assets) — "
      "zero rede, zero R2, zero custo. Números marcados **MEDIDO** saíram desta "
      "máquina; **ESTIMATIVA** = fórmula, extrapolação ou preço publicado. "
      "Latências abaixo de ~16 ms estão no limite do tick do agendador do Windows — "
      "ler como \"rápido demais para medir com precisão neste setup\".")
    a("")
    a("## 1. Escala de itens por museu")
    a("")
    a("| Itens | Build (s) MEDIDO | Payload api/ (MB) MEDIDO | Site total (MB) MEDIDO | "
      "Startup serve (ms) MEDIDO | /collections/items p50/p95 (ms) MEDIDO | "
      "/search p50/p95 (ms) MEDIDO | /items/{id} p50/p95 (ms) MEDIDO |")
    a("|---|---|---|---|---|---|---|---|")
    for s in scales:
        a(f"| {s['items']} | {s['build_s']} | {s['payload_api_mb']} | {s['site_mb']} | "
          f"{s['serve_startup_ms']} | {s['lat_items']['p50']}/{s['lat_items']['p95']} | "
          f"{s['lat_search']['p50']}/{s['lat_search']['p95']} | "
          f"{s['lat_item']['p50']}/{s['lat_item']['p95']} |")
    a("")
    a("Baseline de referência: acervo real do DemoMuseum (463 itens) = 7,3 s de build "
      "local, 36 s de CI com deploy (M3_plano.md).")
    a("")
    if museums:
        a(f"## 2. Escala de museus ({museums['items_por_museu']} itens por instância, mesmo processo)")
        a("")
        a(f"RSS base do processo (sem instância): {museums['rss_base_mb']} MB MEDIDO.")
        a("")
        a("| Instâncias | RSS total (MB) MEDIDO | MB marginais por instância MEDIDO | "
          "/collections/items p50 (ms) MEDIDO |")
        a("|---|---|---|---|")
        for r in museums["rows"]:
            a(f"| {r['instances']} | {r['rss_mb']} | {r['marginal_mb_por_instancia']} | "
              f"{r['lat_items_p50_ms']} |")
        a("")
        marg = [r["marginal_mb_por_instancia"] for r in museums["rows"] if r["instances"] > 1]
        if marg:
            avg = statistics.mean(marg)
            a(f"Marginal médio por instância: **{avg:.1f} MB** MEDIDO. "
              f"Extrapolação **ESTIMATIVA**: 20 museus de {museums['items_por_museu']} itens ≈ "
              f"{museums['rss_base_mb'] + 20 * avg:.0f} MB de RAM no processo host — "
              "a máquina do estúdio comporta; o dimensionamento do App Service (M4) parte daqui.")
            a("")
    a("## 3. Custo por museu (Cloudflare R2) — ESTIMATIVA sobre preço publicado")
    a("")
    a("Preços R2 (tabela pública, out/2026 — confirmar antes de precificar): storage "
      "US$ 0,015/GB·mês; operações Classe A (escrita) US$ 4,50/milhão; Classe B "
      "(leitura) US$ 0,36/milhão; **egress zero**. Câmbio assumido: US$ 1 ≈ R$ 5,60 "
      "(assunção, não medição).")
    a("")
    biggest = scales[-1]
    per_card = biggest["payload_api_mb"] * 1e6 / biggest["items"]
    a(f"- Payload medido por card: **{per_card:.0f} bytes** (média do corpus de "
      f"{biggest['items']} itens, MEDIDO) — JSON puro é desprezível: 10.000 cards ≈ "
      f"{biggest['payload_api_mb']} MB ≈ US$ 0,0002/mês de storage.")
    a("- O custo real é dos **assets do cliente** (fotos/modelos): 2.000 peças × "
      "1 foto de 500 KB ≈ 1 GB ≈ US$ 0,015/mês ≈ R$ 0,08 (ESTIMATIVA).")
    a("- Leituras (Class B): 100 mil páginas/mês com 5 requests ao bucket cada = "
      "500 mil ops ≈ US$ 0,18/mês ≈ R$ 1,00 (ESTIMATIVA).")
    a("- **Conclusão**: na faixa do MVP, R2 é centavos por museu por mês; o custo "
      "que manda é o compute (App Service, M4), não o storage.")
    a("")
    a("## Como reproduzir")
    a("")
    a("```bash")
    a("python -m beta.load                     # tabela completa (reescreve este doc)")
    a("python -m beta.load --scales 500,2000   # parcial")
    a("```")
    a("")
    return "\n".join(add)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="beta.load")
    parser.add_argument("--scales", default="500,2000,5000,10000")
    parser.add_argument("--museums", default="1,2,4,8")
    parser.add_argument("--items-per", type=int, default=500)
    parser.add_argument("--skip-museums", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--doc", default=str(DEFAULT_DOC))
    parser.add_argument("--state", default=str(RAW_DIR / "load-state.json"),
                        help="resumable state: scales already measured are skipped")
    parser.add_argument("--reset", action="store_true",
                        help="discard the state file and re-measure everything")
    args = parser.parse_args(argv)

    run_id = f"{datetime.now(timezone.utc):%Y-%m-%dT%H%M%SZ}"
    machine = _machine_info()
    scales = [int(s) for s in args.scales.split(",") if s.strip()]

    state_path = Path(args.state)
    state = {"scales": {}, "museums": None, "machine": machine, "run_id": run_id}
    if state_path.is_file() and not args.reset:
        state.update(json.loads(state_path.read_text(encoding="utf-8")))
        state["machine"] = machine  # refresh: the machine may have changed

    for n in scales:
        if str(n) in state["scales"]:
            print(f"[load] escala {n}: já medida (state) — pulando", flush=True)
            continue
        print(f"[load] escala {n} itens…", flush=True)
        row = bench_item_scale(n, args.seed)
        state["scales"][str(n)] = row
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        print(f"  build {row['build_s']}s · payload {row['payload_api_mb']}MB · "
              f"startup {row['serve_startup_ms']}ms · search p95 {row['lat_search']['p95']}ms",
              flush=True)

    if not args.skip_museums and state["museums"] is None:
        counts = [int(s) for s in args.museums.split(",") if s.strip()]
        print(f"[load] museus {counts} × {args.items_per} itens…", flush=True)
        state["museums"] = bench_museum_scale(counts, args.items_per, args.seed)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        for r in state["museums"]["rows"]:
            print(f"  {r['instances']} instâncias: RSS {r['rss_mb']}MB "
                  f"(+{r['marginal_mb_por_instancia']}MB/inst)", flush=True)

    results = [state["scales"][k] for k in sorted(state["scales"], key=int)]
    doc = render_report(results, state["museums"], state["machine"],
                        state.get("run_id", run_id))
    Path(args.doc).write_text(doc, encoding="utf-8", newline="\n")
    print(f"[load] state: {state_path}")
    print(f"[load] doc: {args.doc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

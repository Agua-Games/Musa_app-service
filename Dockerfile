# syntax=docker/dockerfile:1
# MUSA app-service — the consumable artifact (M0.4, ADR 0006).
#
# The image packages the builder + the generic frontend + the frozen contract.
# A client repository never contains MUSA code: its CI runs this image with the
# repository mounted, and the builder emits the museum's static site.
#
#   docker run --rm -v ${PWD}:/work ghcr.io/agua-games/musa-app:0.1.0 \
#     build --repo /work --frontend /app/frontend --out /work/_site
#
# Version upgrades on the client side are a one-line change in
# museum.config.json ("musa": "0.2.0") plus a push.

FROM python:3.12-slim AS base

WORKDIR /app

# The builder is a plain Python package; the gate (jsonschema) is its only
# runtime dependency.
COPY builder/ /app/builder/
RUN pip install --no-cache-dir /app/builder

# The generic frontend template. fetch_vendor.py resolves its output relative
# to its own location (<root>/source/assets/vendor), so the repo layout is
# preserved under /app. Demo content and dev-server files are dropped after
# vendoring (the builder would exclude them anyway) to keep the image lean.
COPY source/ /app/source/
COPY tools/fetch_vendor.py /app/tools/fetch_vendor.py
RUN python /app/tools/fetch_vendor.py \
    && rm -rf /app/source/assets/img \
              /app/source/assets/models \
              /app/source/assets/video \
              /app/source/data \
              /app/source/server.mjs \
              /app/source/package.json \
              /app/source/README.md \
              /app/tools \
    && ln -s /app/source /app/frontend

# The frozen contract, for reference inside the artifact (the builder validates
# against its own bundled copy, kept in sync by tests/test_schema_sync.py).
COPY schemas/ /app/schemas/

# The virtual-client harness (M3, ADR 0014/0015): personas + misuse generator +
# invariants. Travelling with the artifact, any client repository can be
# validated by the exact published image it runs:
#   docker run --rm -v ${PWD}:/work --entrypoint python \
#     ghcr.io/agua-games/musa-app:<versão> -m beta.run_beta --repo /work --suite all
COPY beta/ /app/beta/

# ---- production hardening (M4.1) -------------------------------------------
# No bytecode writes and unbuffered logs: the image is meant to run with a
# READ-ONLY root filesystem in production — the only writable paths are the
# mounts the operator provides:
#   - the client repository at /work (build/serve modes), and/or
#   - a scratch tmpfs at /tmp (beta harness, serve overlay via --data-dir).
# Example:  docker run --read-only --tmpfs /tmp -v ${PWD}:/work ...
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root runtime user (production default). Client CI workflows that mount
# the repository and must write build output into it run with `--user root`
# explicitly — batch builds as root on a throwaway runner are acceptable; the
# production runtime (Container Apps) keeps the unprivileged default.
RUN groupadd --system musa && useradd --system --gid musa --uid 1000 musa \
    && chown -R musa:musa /app
USER musa

# Meaningful in serve mode (long-running); batch runs ignore it. uvicorn is
# the container's PID-1 process and shuts down gracefully on SIGTERM.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status==200 else 1)" || exit 1

LABEL org.opencontainers.image.source="https://github.com/Agua-Games/Musa_app-service" \
      org.opencontainers.image.description="MUSA app-service builder: client content repository -> static museum site" \
      org.opencontainers.image.licenses="Proprietary"

ENTRYPOINT ["python", "-m", "musa_build"]
CMD ["--help"]

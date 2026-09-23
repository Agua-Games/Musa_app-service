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

LABEL org.opencontainers.image.source="https://github.com/Agua-Games/Musa_app-service" \
      org.opencontainers.image.description="MUSA app-service builder: client content repository -> static museum site" \
      org.opencontainers.image.licenses="Proprietary"

ENTRYPOINT ["python", "-m", "musa_build"]
CMD ["--help"]

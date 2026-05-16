# syntax=docker/dockerfile:1.7
#
# Single-container deployment for Coolify.
#
# Stage 1 builds the Next.js frontend as a "standalone" Node server.
# Stage 2 builds the Python/Orange backend and copies the frontend artefact
# next to it. At runtime, both processes start side-by-side: uvicorn binds to
# 127.0.0.1:8000 (internal only) and Next.js binds to 0.0.0.0:3000 (the only
# port the container exposes). Next.js rewrites /api/* server-side to the
# backend so the browser only ever talks to one origin.
# -------------------------------------------------------------------

############################
# Stage 1 — Frontend build #
############################
# Pinned to linux/amd64 because PyQt5 doesn't publish arm64 Linux wheels — a
# native arm64 build would try to compile PyQt5 from source and fail without
# qmake. Coolify hosts are almost always x86_64, so this is the right target.
# If you're on an Apple Silicon Mac, the build runs under Rosetta (slower but
# works).
FROM --platform=linux/amd64 node:20-bookworm-slim AS frontend-build

ENV NEXT_TELEMETRY_DISABLED=1 \
    CI=1 \
    PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH

WORKDIR /build

# Install pnpm via corepack (matches the version in lockfile)
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# After build the standalone output is at /build/.next/standalone, the
# static chunks at /build/.next/static, and public assets at /build/public.

#################################
# Stage 2 — Backend + runtime   #
#################################
FROM --platform=linux/amd64 python:3.11-slim AS runtime

# Qt runtime libs — the "with glucose" .pkcls pulls AnyQt → PyQt5 → QPainter
# at unpickle time. We also install nodejs so Next.js standalone can run.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \
    libxcb-xkb1 libxkbcommon-x11-0 \
    libxext6 libsm6 libxrender1 \
    libglib2.0-0 libnss3 libasound2 \
    curl ca-certificates gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && apt-get purge -y --auto-remove gnupg \
 && rm -rf /var/lib/apt/lists/*

ENV QT_QPA_PLATFORM=offscreen \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    INTERNAL_API_URL=http://127.0.0.1:8000 \
    BUNDLED_MODELS_DIR=/app/backend/models \
    UPLOADS_DIR=/app/backend/uploads

WORKDIR /app

# ---- Backend ----------------------------------------------------------------
COPY backend/pyproject.toml /tmp/backend/pyproject.toml
COPY backend/app /tmp/backend/app
RUN pip install --upgrade pip && pip install /tmp/backend

# Keep the .py sources at a known runtime path for clarity in logs.
RUN mkdir -p /app/backend
COPY backend/app /app/backend/app
COPY backend/models /app/backend/models
RUN mkdir -p /app/backend/uploads

# ---- Frontend (standalone output) ------------------------------------------
COPY --from=frontend-build /build/.next/standalone /app/frontend
COPY --from=frontend-build /build/.next/static /app/frontend/.next/static
COPY --from=frontend-build /build/public /app/frontend/public

# ---- Entrypoint -------------------------------------------------------------
COPY scripts/start.sh /usr/local/bin/start.sh
RUN chmod +x /usr/local/bin/start.sh

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:3000/api/health || exit 1

CMD ["/usr/local/bin/start.sh"]

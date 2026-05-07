# ── Stage 1: build the React/Vite SPA ────────────────────────────────────────
FROM node:20-alpine AS ui-build
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# ── Stage 2: Python application ───────────────────────────────────────────────
FROM python:3.12-slim AS base
ARG APT_MIRROR_HOST=""
ARG PIP_INDEX_URL=""
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN if [ -n "${APT_MIRROR_HOST}" ] && [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR_HOST}|g; s|security.debian.org|${APT_MIRROR_HOST}|g" \
        /etc/apt/sources.list.d/debian.sources; \
    fi \
 && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV UV_INDEX_URL=${PIP_INDEX_URL}
RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project
RUN uv pip install neo4j

COPY onto_platform ./onto_platform
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy built UI assets from stage 1
COPY --from=ui-build /ui/dist /srv/ui/dist

RUN useradd --uid 1000 --create-home onto && chown -R onto:onto /app
USER onto

EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]

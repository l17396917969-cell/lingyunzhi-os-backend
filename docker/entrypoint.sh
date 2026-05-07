#!/usr/bin/env bash
set -euo pipefail
case "${1:-serve}" in
  serve)
    uv run alembic upgrade head
    exec uv run uvicorn onto_platform.app:create_app --factory \
      --host "${ONTO_BIND_HOST:-0.0.0.0}" --port "${ONTO_BIND_PORT:-8080}" \
      --proxy-headers --forwarded-allow-ips="*"
    ;;
  cli)
    shift
    exec uv run python -m onto_platform.cli "$@"
    ;;
  *)
    echo "unknown entrypoint command: $1" >&2
    exit 64
    ;;
esac

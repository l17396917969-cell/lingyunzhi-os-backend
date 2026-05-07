#!/usr/bin/env bash
set -euo pipefail
# Live-AI smoke setup. Boots compose, seeds MySQL, prints tokens + mcp.json.

cd "$(dirname "$0")/.."

if [[ -z "${ONTO_SECRET_KEY:-}" ]]; then
  ONTO_SECRET_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
  export ONTO_SECRET_KEY
fi

# Use a sibling MySQL container brought up via compose override (operator-managed)
docker compose -f docker/compose.yaml --env-file <(echo "ONTO_SECRET_KEY=$ONTO_SECRET_KEY") up -d --build

# Wait for the app
until curl -fsS http://127.0.0.1:8080/healthz >/dev/null 2>&1; do sleep 1; done

# Capture the bootstrap token from logs
BOOTSTRAP_TOKEN=$(docker compose -f docker/compose.yaml logs app | grep -oE 'op_[A-Za-z0-9_-]+' | head -1)

# Bring up an extra MySQL container alongside (named `onto-live-mysql`),
# load the logistics fixtures, then register it as a connection via the admin
# MCP tool. (See docs/operator/live-ai-smoke.md for the full handoff.)
echo "BOOTSTRAP_TOKEN=$BOOTSTRAP_TOKEN"
echo
echo "Paste this into ~/.claude/mcp.json (or run 'claude mcp add onto'):"
cat <<EOF
{
  "mcpServers": {
    "onto": {
      "command": "curl",
      "args": ["-N", "-H", "Authorization: Bearer $BOOTSTRAP_TOKEN",
               "-X", "POST", "--data-binary", "@-",
               "http://127.0.0.1:8080/mcp"]
    }
  }
}
EOF

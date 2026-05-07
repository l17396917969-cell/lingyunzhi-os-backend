#!/usr/bin/env bash
# scripts/chat-smoke.sh — drive the full chat lifecycle via HTTP, verify each step.
#
# Prerequisites:
#   - A running onto-platform stack reachable at $ONTO_BASE_URL (default http://127.0.0.1:8080)
#   - $ONTO_BOOTSTRAP_TOKEN exported with an admin/editor token
#   - jq + curl on PATH
#   - tests/fixtures/sql/logistics_minimal_ddl.sql exists in the repo
set -euo pipefail

BASE="${ONTO_BASE_URL:-http://127.0.0.1:8080}"
TOKEN="${ONTO_BOOTSTRAP_TOKEN:?must export ONTO_BOOTSTRAP_TOKEN}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="$REPO_ROOT/tests/fixtures/sql/logistics_minimal_ddl.sql"

echo "==> create session"
SID=$(curl -fsS -X POST "$BASE/chat/sessions" \
  -H "Authorization: Bearer $TOKEN" | jq -r .session_id)
echo "    session_id=$SID"

echo "==> upload SQL fixture"
UPLOAD_ID=$(curl -fsS -X POST "$BASE/chat/sessions/$SID/uploads" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$FIXTURE" | jq -r .upload_id)
echo "    upload_id=$UPLOAD_ID"

echo "==> submit turn"
TID=$(curl -fsS -X POST "$BASE/chat/sessions/$SID/turns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"把 logistics_minimal_ddl.sql 里的所有表加进去\",\"upload_ids\":[\"$UPLOAD_ID\"]}" \
  | jq -r .turn_id)
echo "    turn_id=$TID"

echo "==> stream events (timeout 90s)"
timeout 90 curl -fsS -N \
  -H "Authorization: Bearer $TOKEN" \
  "$BASE/chat/sessions/$SID/stream?turn_id=$TID" || true

echo "==> save session"
curl -fsS -X POST "$BASE/chat/sessions/$SID/save" \
  -H "Authorization: Bearer $TOKEN"
echo "==> done"

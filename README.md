# Onto Platform

Deployable Ontology Platform — a Python FastAPI service that persists a
two-environment `OntologyRegistry` (staging + production), exposes it
through an MCP server (Streamable HTTP) for AI IDE clients, and
bridges to bound SQL data with read-only enforcement and compliance
masking.

## Documents

- Design spec: `docs/superpowers/specs/2026-04-25-ontology-platform-backbone-design.md`
- Implementation plans:
  - `docs/superpowers/plans/2026-04-25-01-backbone.md` (this sub-project)
  - `docs/superpowers/plans/2026-04-25-02-ingestion.md`
  - `docs/superpowers/plans/2026-04-25-03-ui.md`
- Operator runbooks: `docs/operator/`

## Quickstart (dev)

```bash
uv sync --all-groups
ONTO_DATABASE_URL=postgresql+asyncpg://onto:onto@localhost:5432/onto \
  ONTO_SECRET_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  make migrate
make dev
```

The first start prints `ADMIN BOOTSTRAP TOKEN: op_...` to stdout. Capture
it; that's your only path to mint subsequent admin tokens.

## Quickstart (Docker)

```bash
echo "ONTO_SECRET_KEY=$(uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")" > docker/.env
docker compose -f docker/compose.yaml --env-file docker/.env up -d --build
docker compose -f docker/compose.yaml logs app | grep BOOTSTRAP
```

## MCP integration (Claude Code)

Once you have an editor- or admin-scope token (mint via `mint_token`
once you've used the bootstrap), add the server to Claude Code:

```json
{
  "mcpServers": {
    "onto": {
      "transport": "streamable-http",
      "url": "http://127.0.0.1:8080/mcp",
      "headers": {"Authorization": "Bearer op_<your-token>"}
    }
  }
}
```

## Ingestion (file → ontology)

Operators upload schema files and let an LLM-driven agent build the ontology automatically.

**Step 1 — Upload a file** (`.sql`, `.pdf`, `.docx`, `.pptx`, or `.xlsx`):

```bash
curl -X POST http://localhost:8080/admin/ingestion/uploads \
  -H "Authorization: Bearer op_<editor-token>" \
  -F "file=@schema.sql"
# → {"upload_id": "<uuid>", "kind": "sql", ...}
```

**Step 2 — Submit a job**:

```bash
curl -X POST http://localhost:8080/admin/ingestion/jobs \
  -H "Authorization: Bearer op_<editor-token>" \
  -H "Content-Type: application/json" \
  -d '{"upload_ids": ["<uuid>"], "mode": "replace", "instructions": "Build the logistics ontology."}'
# → {"job_id": "<uuid>", "status": "queued"}
```

**Step 3 — Poll for completion**:

```bash
curl http://localhost:8080/admin/ingestion/jobs/<job-id> \
  -H "Authorization: Bearer op_<editor-token>"
# → {"status": "imported", "decisions_report": {...}, ...}
```

**MCP tool** (for AI IDE clients with editor scope):

```
submit_ingestion_job(upload_ids=[...], mode="replace", instructions="...")
get_ingestion_job(job_id="...")
```

Configure the LLM provider via env vars: `ONTO_LLM_BASE_URL`, `ONTO_LLM_API_KEY`, `ONTO_LLM_MODEL`. Any OpenAI- or Anthropic-compatible endpoint (OpenAI, DeepSeek, Volcengine, Anthropic, etc.) is supported via LiteLLM.

## UI (React operator console)

The `ui/` directory contains a React 18 + Vite + TypeScript + TailwindCSS operator
console covering Dashboard, Ontology Browser, Graph View, Diff/Promote, and Ingestion.

### Development

Start the backend in one terminal, the Vite dev server in another:

```bash
# Terminal 1 — backend (proxied by Vite on /api, /admin, /mcp)
make dev

# Terminal 2 — Vite dev server on http://127.0.0.1:5173
cd ui && npm install && npm run dev
```

Open `http://127.0.0.1:5173` in a browser. On the login screen, paste any valid
operator token. To mint one from the CLI:

```bash
# Using the MCP mint_token tool via curl (requires ONTO_BOOTSTRAP_TOKEN):
curl -s -X POST http://127.0.0.1:8080/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ONTO_BOOTSTRAP_TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"mint_token","arguments":{"scope":"editor","label":"my-session"}}}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['structuredContent']['token'])"
```

Paste the `op_...` token into the UI login form and click **Sign in**.

### Playwright e2e suite

Run the full Playwright suite against a live backend:

```bash
export ONTO_BOOTSTRAP_TOKEN="op_..."   # bootstrap admin token from make dev logs
make e2e-ui
```

`make e2e-ui` builds the UI, installs the Chromium browser, and runs all five spec
files: `login`, `browse_graph`, `masking_display`, `ingestion`, `diff_promote`.
Each spec includes axe-core a11y checks. See `scripts/e2e-ui.sh` for prerequisites.

## Tests

```bash
make test            # fast suite: unit + integration (no Docker)
make test-e2e        # heavy suite: Postgres + MySQL testcontainers
make e2e-ai          # live AI smoke (manual)
make e2e-ui          # Playwright UI e2e (requires live backend)
cd ui && npm test    # Vitest unit tests (11 tests, no backend needed)
```

# Ontology Platform — Full Design (Sub-projects 1, 2, 3)

> **Status:** Design (approved by user 2026-04-25)
> **Scope:** All three sub-projects (Backbone server, File ingestion, Web UI) — to be implemented under one combined plan per user direction. §1–§15 specify the Backbone server (S1). §16 specifies File ingestion (S2). §17 specifies the Web UI (S3).

## 1. Overview

The Ontology Platform is a deployable server that turns the existing `onto_skill` modeling workflow into a long-running service. This sub-project delivers the **backbone**: a single Python process that

- persists two named ontology registries — `staging` and `production` — backed by Postgres,
- exposes them through an MCP server (Streamable HTTP transport) for AI IDE clients,
- enforces bearer-token auth with three scopes (`read`, `editor`, `admin`),
- validates every staging mutation against the proto / `ONTOLOGY.md` rules,
- and bridges the ontology to real data: each `ObjectType` / `LinkType` carries an `AssetMapping`, and admins can register SQL connections that the MCP server uses to run scoped, read-only `SELECT`s with compliance-aware result masking.

The headline use case is: a Claude IDE connects to the MCP server with a `read` token, asks "what's in the ontology?", picks an entity, calls `describe_bound_asset`, then calls `query_sql` to fetch real rows — and the server applies compliance masking before returning them.

## 2. Goals

- Two-environment registry: staging is editable; production is what AI consumers read; promote (staging → production) and revert (staging ← production) are first-class operations. One `previous_production` backup slot enables a single-step `undo_promote`.
- Source-of-truth alignment: the proto under `proto/` and `ONTOLOGY.md` are authoritative; the validator ports the rules from the existing `ontology-evaluate` skill into Python.
- MCP-first: every operation an admin or AI client needs is available as an MCP tool. The future REST/UI surface is a thin shim over the same handlers.
- Multi-engine binding: the platform's own metadata lives in Postgres, but bound user-data connections can be Postgres, MySQL, or SQLite. The end-to-end test exercises a Postgres+MySQL setup using the repo's own SQL files.
- Safe by default: read-only enforcement on every bound-data query (AST gate + read-only transaction), compliance masking on restricted columns, optimistic concurrency on staging writes, structured errors with no silent partial writes.

## 3. Non-goals (deferred to future work)

The combined plan covers Sub-projects 1, 2, and 3 (Backbone, Ingestion, UI). The following are still out of scope and not part of V1:

- Writeback to bound DBs (the proto's `writeback_*` fields are accepted in stored definitions but never executed).
- Action execution (`ActionType` definitions are stored and validated, but no runner is included).
- Form-based entity editor in the UI — the UI in V1 is browse + diff + ingest; entity edits happen via MCP from a Claude IDE (or directly via the registry CRUD tools from any MCP client).
- Admin views in the UI for tokens, connections, audit log — these stay MCP-only in V1 (admin-scope MCP tools handle them).
- Multi-tenant orgs, SSO, fine-grained per-row ACL, full version history, metrics/tracing endpoints, rate limiting.
- Real-time push for ingestion progress (UI polls every 2s instead of SSE/WebSocket).

## 4. Architecture

A single FastAPI process serves both surfaces:

- `POST /mcp` — Streamable HTTP MCP endpoint, mounted via the official `mcp` Python SDK (`mcp.server.fastmcp`). All ontology and data-access operations are exposed as MCP tools.
- `POST /admin/*` — REST endpoints for token mgmt and connection mgmt, intended for the future web UI. Every REST endpoint has a one-to-one MCP-tool counterpart so an admin operating from a Claude IDE has full functionality without the UI.

Streamable HTTP is the only viable transport: stdio is local-only, SSE is deprecated, and the user's flow ("local AI IDE access MCP server") is inherently remote.

External SQL access goes through SQLAlchemy async engines, one per registered connection, cached process-wide and configured read-only at the engine level (with belt-and-suspenders SQL AST validation per query — see §8).

### 4.1 Module layout

```
onto_platform/
├── app.py                # FastAPI app factory, lifespan, MCP mount
├── config.py             # env-driven Settings (pydantic-settings)
├── db.py                 # async SQLAlchemy engine + session for platform metadata
├── auth.py               # token hashing (argon2id), scope dependency
├── registry/
│   ├── store.py          # load/save staging | production | previous_production
│   ├── validator.py      # proto-aware validation (port of ontology-evaluate)
│   ├── crud.py           # fine-grained mutations on a registry
│   └── lifecycle.py      # promote / revert / undo_promote
├── connections/
│   ├── store.py          # CRUD on `connections` table (DSN encrypted at rest)
│   ├── pool.py           # per-connection async engine cache, read-only enforced
│   └── data_query.py     # describe_bound_asset, query_sql, masking
├── mcp_server.py         # tool registrations grouped by scope (read/editor/admin)
├── admin_api.py          # REST routes for the future UI
└── cli.py                # bootstrap-admin, db-migrate, rotate-secret, dump/restore
tests/
  unit/
  integration/
  e2e/
  fixtures/
    sql/
    ontology/
migrations/               # alembic
docker/
  Dockerfile
  compose.yaml
```

### 4.2 Postgres schema (platform metadata)

| Table | Columns | Notes |
|---|---|---|
| `registries` | `env` PK ∈ {`staging`, `production`, `previous_production`}; `payload` jsonb (full `OntologyRegistry`); `version` int; `updated_at` timestamptz; `updated_by_token_label` text; `last_commit_message` text nullable | Always exactly three rows; an initial migration seeds them empty. `version` increments on every write and powers optimistic concurrency. |
| `api_tokens` | `id` uuid PK; `token_hash` text unique (argon2id); `token_prefix` text indexed (first 8 chars of base64 token, lookup hint); `scope` text ∈ {`read`,`editor`,`admin`}; `label` text; `created_at`; `created_by_token_id` nullable; `revoked_at` nullable | Plaintext token shown once at mint; never stored. |
| `connections` | `id` uuid PK; `label` text unique; `kind` text ∈ {`postgres`,`mysql`,`sqlite`}; `dsn_encrypted` bytea (Fernet, key from `ONTO_SECRET_KEY`); `created_at`; `last_probe_ok_at` timestamptz nullable | Server probes with `SELECT 1` before persisting on add/update. |
| `audit_log` | `id` bigserial PK; `ts`; `token_id` nullable (null for requests rejected before auth resolves a row, e.g. `UNAUTHORIZED` from a missing/malformed header); `token_label` snapshot; `scope` snapshot; `tool` text; `args_summary` jsonb (sanitized — DSNs redacted, SQL bodies truncated to 500 chars with an `sql_truncated: true` marker); `outcome` text; `error_code` nullable | Append-only. Written from every MCP dispatcher and every REST mutation. |

### 4.3 Key invariants

- The three `registries` rows always exist. The store refuses to operate if any is missing (readiness probe fails).
- `previous_production` is **only** written by `promote_staging_to_production`, and **only** read or cleared by `undo_promote`. Nothing else touches it.
- `revert_staging_to_production` writes `staging`, never touches `production` or `previous_production`.
- Every CRUD path round-trips through `validator.py` before commit; on failure, the transaction rolls back and the response is `VALIDATION_FAILED`. There is no partial-write code path anywhere.
- DSNs never leave the process in plaintext: not in logs, not in `audit_log`, not in REST responses.

## 5. MCP tool surface

All tools require a valid bearer token (`Authorization: Bearer <token>`); scope is enforced per tool. Tool names are `snake_case`. Inputs and outputs are JSON Schemas derived from the proto messages where applicable. Every dispatch writes one `audit_log` row.

### 5.1 Read-scope tools (available to `read`, `editor`, `admin`)

| Tool | Purpose |
|---|---|
| `get_registry(env)` | Return the full `OntologyRegistry` for `staging` or `production`. |
| `list_object_types(env, filter?)` | Compact listing `{rid, api_name, display_name, lifecycle_status}`. `filter` matches against `api_name` and `display_name` substrings. |
| `list_link_types(env, filter?)` | Same shape for links. |
| `list_interface_types(env, filter?)` | Same for interfaces. |
| `list_shared_property_types(env, filter?)` | Same for shared properties. |
| `list_action_types(env, filter?)` | Same for actions. |
| `get_entity(env, rid)` | Return one entity definition by RID, regardless of kind. |
| `find_by_api_name(env, api_name, kind?)` | Resolve `api_name` → entity. Optional `kind` narrows the search. |
| `describe_bound_asset(env, object_or_link_rid)` | Returns `{connection_id, connection_label, asset_path, columns: [{api_name, physical_column, data_type, sensitivity, masking_strategy}]}`. The single "what do I query and how do I read it back?" tool the AI uses before calling `query_sql`. |
| `query_sql(connection_id, sql, max_rows?, timeout_ms?)` | Run a SELECT-only statement against a registered connection. See §8 for the safety envelope and masking pipeline. |
| `whoami()` | Return `{token_label, scope, server_version}`. Useful for AI clients to self-check on session start. |

### 5.2 Editor-scope tools (available to `editor`, `admin`) — operate on staging only

All editor mutations accept an optional `expected_version` parameter. If it doesn't match the current `staging.version`, the call fails with `STALE_VERSION` and no write occurs. This is the optimistic-concurrency mechanism — multi-writer-safe without explicit locking.

| Tool | Purpose |
|---|---|
| `validate_staging()` | Run the validator on the persisted staging without writing. Returns `[{severity, code, path, message}]`. |
| `put_shared_property_type(definition)` | Upsert by RID. Validator runs on the candidate registry; on error → `VALIDATION_FAILED`, no write. |
| `delete_shared_property_type(rid)` | Refuses if anything still references it (`REFERENCED` with the referrer list). |
| `put_interface_type(definition)` | Upsert. |
| `delete_interface_type(rid)` | Refuses on inbound references. |
| `put_object_type(definition)` | Upsert. Includes the entity's embedded `property_types` map. |
| `delete_object_type(rid)` | Refuses on inbound references. |
| `put_link_type(definition)` | Upsert. |
| `delete_link_type(rid)` | Refuses on inbound references. |
| `put_action_type(definition)` | Upsert. |
| `delete_action_type(rid)` | Refuses on inbound references. |
| `import_full_registry_to_staging(registry, mode)` | Coarse path used by the future ingestion service. `mode = replace` overwrites staging entirely; `mode = merge` upserts each entity. Validator must pass on the resulting registry before commit. |
| `set_asset_mapping(object_or_link_rid, asset_mapping)` | Convenience for binding/unbinding a connection without re-sending a full put. Validates that `read_connection_id` resolves. |

### 5.3 Admin-scope tools (available to `admin` only)

| Tool | Purpose |
|---|---|
| `promote_staging_to_production(commit_message)` | Atomically: `previous_production ← production`, `production ← staging`. Validator must pass on staging first; failure → `VALIDATION_FAILED`. `commit_message` recorded on the production row. |
| `revert_staging_to_production()` | Overwrite `staging` with current `production`. Discards staging edits. |
| `undo_promote()` | Restore `previous_production → production`, then clear the `previous_production` slot. One-shot — second call returns `UNDO_UNAVAILABLE`. |
| `mint_token(scope, label)` | Returns `{token, token_id}`. Plaintext shown once; never retrievable later. |
| `revoke_token(token_id)` | Sets `revoked_at`. Subsequent uses of the token fail with `UNAUTHORIZED`. |
| `list_tokens()` | Returns metadata only (id, scope, label, created_at, created_by, revoked_at). No plaintext, no hash. |
| `add_connection(label, kind, dsn)` | Probes with `SELECT 1` (5s timeout) before persisting. DSN encrypted at rest. |
| `update_connection(id, ...)` / `delete_connection(id)` | Delete refuses if any AssetMapping in either env still references the connection (`REFERENCED`). |
| `list_connections()` | Returns metadata + last successful probe timestamp. Never returns DSN material. |

### 5.4 Tool descriptions

Tool docstrings are derived from `ONTOLOGY.md`, including RID conventions, `api_name` rules, and the staging/production lifecycle. A Claude IDE that calls `tools/list` therefore gets crisp, self-explanatory descriptions — this is what makes the "AI asks 'what's in the ontology'" flow pleasant rather than confusing. Section 11 (live AI smoke test) is the human-in-the-loop check that the descriptions actually land.

## 6. Authentication

### 6.1 Bootstrap

On first startup, if the `api_tokens` table is empty, the server generates a 32-byte URL-safe random token, prints it once to stdout

```
ADMIN BOOTSTRAP TOKEN: op_<base64url>
```

and stores its argon2id hash with `scope = admin`, `label = "bootstrap"`. The operator captures it from container logs (`docker compose logs app | grep BOOTSTRAP`). There is no other path — once the table is non-empty, no further bootstrap tokens are emitted, and the operator is expected to mint replacement admin tokens via `mint_token` before revoking the bootstrap one.

### 6.2 Token format and verification

- Tokens are 32 random bytes, base64url-encoded, prefixed `op_`.
- The DB stores `token_hash` (argon2id) and `token_prefix` (first 8 chars of the encoded token, indexed). Lookup uses `token_prefix` as a hint, then argon2id verify on the candidate row(s) — constant-time per row, fail-closed.
- Verification additionally checks `revoked_at IS NULL`. Revoked tokens are kept (for audit), not deleted.

### 6.3 Per-request middleware

A FastAPI dependency `require_scope(min_scope)`:

1. Reads `Authorization: Bearer <token>`. Missing or malformed → `UNAUTHORIZED`.
2. Resolves to a token row via prefix + argon2id. No match → `UNAUTHORIZED`.
3. Checks `revoked_at IS NULL`. Revoked → `UNAUTHORIZED`.
4. Compares `scope ≥ min_scope` (where `read < editor < admin`). Insufficient → `FORBIDDEN`.
5. Stashes `(token_id, label, scope)` on the request context.

The MCP tool dispatcher wraps each tool function with the right scope dependency at registration time. The `tools/list` response is filtered per token: a `read` token sees only read-scope tools, an `editor` token sees read + editor, etc. This makes the available surface self-documenting per role.

### 6.4 Audit trail

Every dispatch (MCP tool or REST endpoint) writes one `audit_log` row. `args_summary` is sanitized — DSNs are replaced with `***`, SQL bodies are truncated to 500 chars with an `sql_truncated: true` marker (distinct from the `truncated` flag in `query_sql` responses, which signals row truncation), full ontology payloads are summarized as `{entity_counts: {...}}`. The full ontology payload is never logged (it would balloon the table); auditors needing the actual content read the `registries` row directly.

## 7. Validator

`registry/validator.py` is a pure function

```python
def validate(registry: OntologyRegistry, *, connection_ids: set[str]) -> list[Finding]:
    ...
```

It ports the rules from the existing `ontology-evaluate` skill (under `.claude/commands/ontology-evaluate.md`) into Python, organized as discrete checker functions so each is individually unit-testable.

### 7.1 Rule categories

- **Structural.** Top-level shape, required fields present, RID format `ri.{prefix}.{uuid}` (with prefix matching the entity kind: `shprop`, `prop`, `iface`, `obj`, `link`, `action`), `api_name` regex `^[a-z][a-z0-9]*(_[a-z0-9]+)*$`, `LifecycleStatus` and other enum values valid.
- **Referential integrity.** Every `*_rid` field resolves to an entity of the right kind in the same registry. PropertyType references are scoped — `inherit_from_shared_property_type_rid` must point at a `SharedPropertyType`; `extends_interface_type_rids` must point at `InterfaceType`s of the same `category`.
- **Interface category rules.** `OBJECT_INTERFACE` may carry `link_requirements`, must not carry `object_constraint`. `LINK_INTERFACE` is the inverse. No extension cycles. `INTERFACE_CATEGORY_INVALID` is rejected.
- **PropertyType backing.** Exactly one of `physical_column` / `virtual_expression` is set (oneof; enforced at proto level but re-checked here). If `inherit_from_shared_property_type_rid` is set, the local `data_type` must match the inherited one.
- **AssetMapping.** If present and non-empty, `read_connection_id` must be in the supplied `connection_ids` set (or be empty for un-bound types — flagged as `WARNING`, not `ERROR`, since not every type needs to be bound). `writeback_connection_id` is accepted but not validated for liveness (writeback is out of scope).
- **Cross-property validation expressions.** Every `{api_name}` reference inside `CrossPropertyExpression.expression` must resolve to a property defined on the same entity.
- **Object/Link primary keys.** Every `primary_key_property_type_rid` must point at a `PropertyType` that exists on the entity.

### 7.2 Where the validator runs

- Every fine-grained mutation tool (`put_*`, `delete_*`, `set_asset_mapping`) builds a *candidate* registry by applying the proposed change to the current staging, runs the validator, and only commits if there are no `ERROR`-severity findings.
- `validate_staging()` runs it on the persisted staging without touching it, returning all findings (including `WARNING`s).
- `import_full_registry_to_staging` runs it on the proposed registry; failure → no write.
- `promote_staging_to_production` re-runs it as a final gate against the live `connections` table — connections may have been deleted since the staging edits, so validation that passed at edit time can legitimately fail at promote time.

### 7.3 Finding shape

```json
{
  "severity": "ERROR" | "WARNING",
  "code": "RID_FORMAT" | "REF_NOT_FOUND" | "INTERFACE_CATEGORY_MISMATCH" | ...,
  "path": "object_types[ri.obj.123].property_types[battery_level].inherit_from_shared_property_type_rid",
  "message": "Referenced shared property type ri.shprop.999 does not exist",
  "details": {...}
}
```

Codes are stable strings — clients can route on them.

## 8. Bound-data query path

This is the headline path: AI client picks an entity from the ontology, asks where it lives, then asks for rows.

### 8.1 Connection registration

`add_connection(label, kind, dsn)`:

1. Decrypts and parses the DSN locally.
2. Builds a temporary engine and runs `SELECT 1` with a 5s timeout. Failure → `CONNECTION_PROBE_FAILED` with `details.driver_error`.
3. On success, encrypts the DSN with Fernet using `ONTO_SECRET_KEY` (from env, never logged), persists, sets `last_probe_ok_at`. Returns `{id, label, kind}`.

`update_connection` re-probes; `delete_connection` refuses if any AssetMapping in either env still references the connection (`REFERENCED`, with the referrer list). `ONTO_SECRET_KEY` rotation is handled by a CLI command (`onto-admin rotate-secret`) that re-encrypts every row.

### 8.2 Engine cache and read-only enforcement

`connections/pool.py` keeps a per-connection cache of SQLAlchemy async engines. On first use, the DSN is decrypted, the engine is created with `execution_options(readonly=True)`, and:

- For Postgres: every session begins with `SET TRANSACTION READ ONLY` and `SET LOCAL statement_timeout = ...`.
- For MySQL: every session sets `SET SESSION TRANSACTION READ ONLY` and `SET SESSION MAX_EXECUTION_TIME = ...`.
- For SQLite: open in `mode=ro` URI mode.

The cache is invalidated on `update_connection` / `delete_connection`.

### 8.3 The `query_sql` pipeline

`query_sql(connection_id, sql, max_rows?, timeout_ms?)`:

1. **AST gate** (suspenders). Parse `sql` with `sqlglot.parse(sql, read=<dialect>)`. Reject if:
   - Not exactly one statement (`SQL_REJECTED`, reason `MULTIPLE_STATEMENTS`).
   - Root node is not `SELECT`, `UNION`, or `WITH` whose terminal is a `SELECT`.
   - The AST contains any `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CALL`, `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `GRANT`, `REVOKE`, `COPY`, `LOAD`, `LOCK`, `RENAME`, or `SET ROLE` node anywhere.
   - The AST contains a comment node with embedded SQL fragments (covers `/*+ hints */ DROP TABLE x` style attempts).
2. **Read-only execution** (belt). Run inside a read-only transaction with the configured timeout (default 30s). Server enforces a row cap by inspecting the parsed AST: if the outermost SELECT has no `LIMIT` clause, or has a `LIMIT` strictly greater than `max_rows + 1`, the AST is rewritten to apply `LIMIT max_rows + 1`; otherwise the user's `LIMIT` is left intact. After execution, if the result holds exactly `max_rows + 1` rows, mark `truncated: true` in the response and discard the extra row.
3. **Compliance masking.** For each result column, attempt to resolve it back to a `PropertyType`. Resolution uses the **AST**, not the column-name heuristic, to defeat aliasing: for each output column we walk the parsed SELECT's projection list, find the underlying source expression, and resolve only when the source is a direct column reference (table-qualified or unqualified) into a registered AssetMapping's `physical_column`. Aliased columns (`SELECT cost_price AS foo`) still resolve to `cost_price` and therefore still get masked. Computed expressions (`cost_price * 1.1`, `MIN(cost_price)`) do NOT resolve and are conservatively masked **as if they carried the highest sensitivity of any source column they reference** — so derived values can't be used to leak restricted data. Columns the resolver cannot trace back to any AssetMapping are returned unmasked but listed in `unresolved_columns` for client awareness. If the resolved property has `compliance.sensitivity ≥ CONFIDENTIAL` and a non-`MASK_NONE` `MaskingStrategy`, apply the strategy:
   - `MASK_NULLIFY` → `null`
   - `MASK_REDACT_FULL` → `"***"`
   - `SHOW_LAST_4` → `"****" + value[-4:]` (string), or `null` if value too short
   - `SHOW_FIRST_2` → `value[:2] + "****"`
   - `MASK_EMAIL_DOMAIN` → `local + "@***"`
   - `MASK_EMAIL_USER` → `"***" + "@" + domain`
   - `MASK_PHONE_MIDDLE` → preserve first 3 + last 4, mask middle
4. **Response**:

```json
{
  "columns": [{"name": "...", "data_type": "...", "resolved_property_rid": "..."}],
  "rows": [[...], ...],
  "row_count": 42,
  "truncated": false,
  "masked_columns": ["cost_price"],
  "unresolved_columns": []
}
```

Defaults: `max_rows = 1000` (cap 10000), `timeout_ms = 30000` (cap 120000). All caps are `config.py` env-tunable.

## 9. Lifecycle: promote, revert, undo

Implemented in `registry/lifecycle.py`. Each operation is a single Postgres transaction.

### 9.1 `promote_staging_to_production(commit_message)`

```
BEGIN;
  -- final validation gate
  validate(staging.payload, connection_ids = current_connection_ids)
    -- if any ERROR -> ROLLBACK; return VALIDATION_FAILED

  -- atomic rotation
  UPDATE registries SET payload = (production.payload), version = version + 1,
         updated_at = now(), updated_by_token_label = $label
    WHERE env = 'previous_production';
  UPDATE registries SET payload = (staging.payload), version = version + 1,
         updated_at = now(), updated_by_token_label = $label,
         last_commit_message = $commit_message
    WHERE env = 'production';
COMMIT;
```

### 9.2 `revert_staging_to_production()`

```
BEGIN;
  UPDATE registries SET payload = (production.payload), version = version + 1,
         updated_at = now(), updated_by_token_label = $label
    WHERE env = 'staging';
COMMIT;
```

### 9.3 `undo_promote()`

```
BEGIN;
  -- if previous_production.payload is empty (initial) -> ROLLBACK; return UNDO_UNAVAILABLE
  UPDATE registries SET payload = (previous_production.payload), version = version + 1,
         updated_at = now(), updated_by_token_label = $label
    WHERE env = 'production';
  UPDATE registries SET payload = '<empty registry>', version = version + 1
    WHERE env = 'previous_production';
COMMIT;
```

The "empty registry" sentinel is an `OntologyRegistry` with the documented `version` string `"__empty__"` and all maps empty. The store treats this value as "slot not in use" for `undo_promote` purposes. Reads of `previous_production` are not exposed via MCP — there is no `get_registry("previous_production")`.

## 10. Error model

Every MCP tool returns either a typed result or a structured error `{code, message, details?}`. Codes are stable.

| Code | Meaning |
|---|---|
| `UNAUTHORIZED` | Missing, invalid, or revoked token. |
| `FORBIDDEN` | Token scope insufficient for the tool. |
| `NOT_FOUND` | RID, env, or connection not found. |
| `VALIDATION_FAILED` | One or more `ERROR` findings; `details.findings` lists them all. |
| `STALE_VERSION` | Optimistic-concurrency mismatch on staging write; `details.current_version` returned so client can retry. |
| `REFERENCED` | Delete refused; `details.referrers` lists `[{rid, kind, field}, ...]`. |
| `SQL_REJECTED` | AST gate refused the statement; `details.reason` is one of `MULTIPLE_STATEMENTS`, `NOT_SELECT`, `WRITE_NODE_<NAME>`, `EMBEDDED_SQL_IN_COMMENT`, `PARSE_ERROR`. |
| `SQL_TIMEOUT` | Connection-side timeout fired. |
| `SQL_ROW_LIMIT` | Row cap exceeded (only emitted in strict-mode; default mode returns `truncated: true` instead). |
| `CONNECTION_PROBE_FAILED` | `add_connection` / `update_connection` could not run `SELECT 1`; `details.driver_error`. |
| `UNDO_UNAVAILABLE` | `undo_promote` called when `previous_production` slot is empty. |

There are no silent partial writes. Every mutation is a single Postgres transaction; any error rolls everything back. Errors carry enough machine-readable detail that an AI client can react usefully — for example, on `VALIDATION_FAILED` with a `REF_NOT_FOUND` finding, the AI can decide to create the missing dependency first and retry.

## 11. Testing strategy

### 11.1 Unit tests

- `tests/unit/test_validator.py` — one test per rule from §7.1, both pass and fail cases. This is the highest-value test surface in the project, so it gets the deepest coverage. Each rule's test asserts the exact `code` and `path` in the resulting `Finding`.
- `tests/unit/test_sql_ast_gate.py` — known-bad statements (multi-statement, comment-injected DDL, stacked queries via `;`, vendor-specific writes like Postgres `COPY`, MySQL `LOAD DATA INFILE`, `WITH ... DELETE`). A red-team fixture file (`tests/fixtures/sql_redteam.txt`) enumerates them. Every entry must produce `SQL_REJECTED`. Known-good statements (plain SELECT, CTEs, UNIONs, window functions) must pass.
- `tests/unit/test_masking.py` — table-driven for every `MaskingStrategy` × representative inputs (including edge cases: empty string, value shorter than the mask reveal length, non-string values for `MASK_NULLIFY`).
- `tests/unit/test_auth.py` — argon2id verify, scope ordering, revocation, `tools/list` filtering by scope.

### 11.2 Integration tests (testcontainers)

`tests/integration/` boots an ephemeral Postgres container (testcontainers-python). Tests run the real app against it.

- Full registry round-trip: load fixture → `import_full_registry_to_staging` → `validate_staging` → `promote_staging_to_production` → `get_registry("production")` matches the fixture.
- Promote/revert/undo state machine: every transition combination, including double-promote (`previous_production` slot churns correctly), `undo_promote` after `revert`, `undo_promote` from cold start (`UNDO_UNAVAILABLE`).
- Optimistic concurrency: two concurrent `put_object_type` calls, both passing the same `expected_version` they read; one wins, the other gets `STALE_VERSION` with `details.current_version` reflecting the winning write. A second test verifies that omitting `expected_version` makes the call last-write-wins (no conflict surfaced).
- Token scope matrix: every tool × every scope; assert each cell either succeeds or returns the right `FORBIDDEN`.
- Audit log: every successful and failed dispatch produces one `audit_log` row with the expected `tool`, `scope`, `outcome`.

No mocked database anywhere. Sqlite stand-ins are not used for these tests because the app uses Postgres-specific features (`SET LOCAL statement_timeout`, JSONB).

### 11.3 MCP contract tests

`tests/integration/test_mcp_contract.py` — uses the official `mcp` Python SDK as a real client over Streamable HTTP, against the same testcontainers stack.

- `tools/list` returns the expected set of tools per scope; descriptions are non-empty and reference the concepts from `ONTOLOGY.md`.
- Argument schemas validate as expected: well-formed args succeed, malformed args produce a clean validation error from the SDK before reaching the server.
- End-to-end `query_sql` against a seeded test connection returns rows with the documented response shape, including `masked_columns`.

### 11.4 End-to-end test using the repo's SQL files

The single test that proves the whole headline flow works against realistic data.

**Test fixtures (committed under `tests/fixtures/`):**

- `tests/fixtures/sql/logistics_ddl.sql` — copy of `智能物流系统9张表建表语句.sql`. Schema: `BO_DELIVERY_TASK_DETAIL`, `MD_MODEL`, `BO_SORTING_PLAN_DETAIL`, `MD_WAREHOUSE_LOCATION`, `BO_SORTING_PLAN`, `MD_OPERATION`, `MD_STATION`, `BW_STOCK_LEDGER`, `MD_MATERIAL`. MySQL syntax (backticks, `ENGINE=InnoDB`).
- `tests/fixtures/sql/scheduling.sql` — copy of `初始5张表sql导入语句.sql` (already includes seed rows for the aviation production-scheduling tables, e.g., `daily_plan`).
- `tests/fixtures/sql/logistics_seed.sql` — small hand-written INSERTs covering the 9 logistics tables (~10 rows each: a couple of materials, stations, warehouse locations, one sorting plan with a few details, one delivery task with a few details, a handful of stock-ledger entries). Just enough that join queries return non-empty results.
- `tests/fixtures/ontology/logistics_registry.json` — hand-authored `OntologyRegistry` covering a representative slice:
  - SharedPropertyTypes: `code`, `name`, `quantity`, `cost_price`. `cost_price` declared with `compliance.sensitivity = CONFIDENTIAL` and `masking = MASK_REDACT_FULL` so the masking pipeline actually fires.
  - InterfaceType: `Trackable` (`OBJECT_INTERFACE`, requires `code`).
  - ObjectTypes: `Material` (binds `MD_MATERIAL`), `Station` (binds `MD_STATION`), `WarehouseLocation` (binds `MD_WAREHOUSE_LOCATION`), `DeliveryTask` (binds `BO_DELIVERY_TASK_DETAIL`). All implement `Trackable`.
  - LinkType: `material_stocked_at` (Material ↔ WarehouseLocation, binds `BW_STOCK_LEDGER`).

**Stack used by `tests/e2e/`:**

- Postgres container — platform metadata (registries, tokens, connections, audit_log).
- MySQL container — bound user data; entrypoint loads `logistics_ddl.sql` + `logistics_seed.sql` + `scheduling.sql`.
- The platform process runs in-process via `httpx.ASGITransport` against the FastAPI app for speed; an alternative subprocess mode is used by one test to verify that the bootstrap admin token is actually emitted to stdout.

**Scripted MCP-client e2e (`tests/e2e/test_ai_task_flow.py`, runs in CI).** Uses the `mcp` Python SDK as the client. Scenarios:

1. *Bootstrap & setup.* Capture bootstrap admin token from process stdout; mint a `read` and an `editor` token; `add_connection("logistics_mysql", "mysql", <dsn>)` succeeds with probe; `import_full_registry_to_staging(logistics_registry.json, mode="replace")` passes validation; `promote_staging_to_production(commit_message="initial seed")` succeeds.
2. *Discovery flow.* With the read token: `tools/list` exposes only read-scope tools; `list_object_types("production")` returns the 4 fixture types; `describe_bound_asset(material_rid)` returns the right MySQL table and column→property mapping including the `cost_price` masking metadata.
3. *Headline AI flow.* `query_sql(logistics_mysql, "SELECT material_code, material_name, cost_price FROM MD_MATERIAL ORDER BY material_code LIMIT 5")` returns rows; assert `cost_price` values are `"***"` and the column is listed in `masked_columns`; assert `material_name` is unmasked; assert row count and ordering match the seed.
4. *Cross-engine check.* Same pipeline against the scheduling-domain table — `query_sql(logistics_mysql, "SELECT * FROM daily_plan WHERE plan_status='执行中'")` returns the seeded UTF-8 Chinese-text rows correctly (round-trip sanity through JSON).
5. *Negative cases.* `query_sql(..., "DROP TABLE MD_MATERIAL")` → `SQL_REJECTED` with `reason=WRITE_NODE_DROP`; `query_sql(..., "SELECT 1; DROP TABLE x")` → `SQL_REJECTED` with `reason=MULTIPLE_STATEMENTS`; `query_sql` with `read` token works, with no token → `UNAUTHORIZED`; `put_object_type` with the read token → `FORBIDDEN`; `promote_staging_to_production` with editor token → `FORBIDDEN`.
6. *Lifecycle.* Editor token edits staging (`put_object_type` adds a new ObjectType `Pilot`); admin promotes; production now contains `Pilot`; `undo_promote` rolls it back; second `undo_promote` returns `UNDO_UNAVAILABLE`.
7. *Validator gate.* Build a deliberately broken registry (LinkType pointing at a non-existent ObjectType); `import_full_registry_to_staging` returns `VALIDATION_FAILED` with the dangling RID surfaced in `details.findings[*].path`; staging is unchanged.

**Live AI smoke test (`make e2e-ai`, NOT in CI).** Same compose stack, but instead of a scripted MCP client, the make target prints an `mcp.json` snippet (with the test server URL + a freshly minted editor token) that the operator pastes into Claude Code. The operator then runs a documented checklist of canonical prompts:

1. *"What object types are in the production ontology?"* — expect `list_object_types` and a clean Chinese-friendly summary.
2. *"Find the 5 materials with the lowest stock."* — expect `describe_bound_asset` then `query_sql` joining `BW_STOCK_LEDGER` to `MD_MATERIAL`.
3. *"Show me delivery tasks that are still in progress."* — same pattern against `BO_DELIVERY_TASK_DETAIL`.
4. *"Add a new ObjectType called Pilot with a `name` property."* — expect `put_shared_property_type` then `put_object_type`; `validate_staging` clean.
5. *"Now promote staging to production."* — expect `promote_staging_to_production`. (Will fail with editor token; AI should report the `FORBIDDEN` and ask the operator for an admin token — that itself is a UX check.)
6. *"Drop the `daily_plan` table."* — expect the AI to attempt `query_sql` and report the `SQL_REJECTED` error gracefully without retrying.

The checklist ships in `docs/operator/live-ai-smoke.md` with expected/observed slots for each prompt so operator runs are recordable. Not blocking CI, but a release-checklist item — it's the only way to catch tool-description and ergonomic problems that scripted tests miss.

The smoke runner also captures the IDE's MCP tool-call trace into `docs/operator/live-ai-smoke-runs/<date>.json` so each run is auditable. Reviewers diff against the previous run to spot regressions in tool selection or argument shapes.

### 11.5 Security, property-based, and resilience tests

These cut across all three sub-projects.

**Security tests** (`tests/security/`):

- *Masking bypass via column aliases.* `query_sql` with `SELECT cost_price AS foo, cost_price * 1.1 AS bar FROM MD_MATERIAL` — assert both `foo` and `bar` are masked. Assert the response's `masked_columns` list contains both. Then with subquery: `SELECT inner_cp AS leak FROM (SELECT cost_price AS inner_cp FROM MD_MATERIAL) t` — same mask-through-aliases assertion.
- *Masking on aggregations.* `SELECT MIN(cost_price), AVG(cost_price), COUNT(*) FROM MD_MATERIAL` — assert `MIN(cost_price)` and `AVG(cost_price)` are masked (because they reference a restricted source column), `COUNT(*)` is unmasked.
- *Token plaintext leakage.* Call `mint_token`, then dump every `audit_log` row written during the call — assert no row contains the returned plaintext token (search by substring). Repeat for the `register_upload` MCP tool which carries base64 content.
- *DSN leakage in error paths.* Register a malformed connection string deliberately containing `password=topsecret`; assert that (a) `CONNECTION_PROBE_FAILED.details.driver_error` does NOT contain `topsecret`, (b) no `audit_log` row contains `topsecret`, (c) no JSON log line on stdout contains it.
- *Audit log args sanitization.* Submit `query_sql` with a 5KB SQL body — assert the recorded `args_summary.sql` is exactly 500 chars + the `sql_truncated: true` marker.
- *Cross-environment write protection.* Try every editor-scope `put_*` tool with `env=production` (the tools should not even accept that arg) — confirm a parameter-validation error, not a write to production.

**Property-based tests** (`tests/property/`, hypothesis):

- *Validator never crashes.* Strategy: generate randomly-shaped (possibly invalid) `OntologyRegistry` payloads. Run validator. Assert: returns a list of findings, never raises.
- *Validator monotonicity.* Generate a valid registry, apply a single mutation that violates exactly one rule, run validator: assert the corresponding finding code appears.
- *Diff is reflexive and antisymmetric.* `diff(reg, reg) == empty`; `diff(a, b)` and `diff(b, a)` should have swapped added/removed lists with identical modified lists.
- *JSON round-trip is identity.* Serialize → deserialize → assert equal to original. (Catches accidental loss-of-precision on numeric properties, ordering issues in maps.)
- *Promote/revert/undo state-machine invariants.* Hypothesis `RuleBasedStateMachine` driving sequences of {promote, revert, undo, edit}. Invariants: production is always validator-clean; if `previous_production` is non-empty, undo restores it exactly; double-undo always returns `UNDO_UNAVAILABLE`.

**Resilience tests** (`tests/resilience/`):

- *Promote → undo → promote sequence.* Edit staging A, promote (production = A, prev = empty); edit staging A', promote (production = A', prev = A); undo (production = A, prev = empty); edit staging A''; promote (production = A'', prev = A). Verify `previous_production` is correctly re-populated each time.
- *Promote during active ingestion.* Submit ingestion job; while it's `agent_running`, run `promote_staging_to_production` from a separate admin token. The agent's working copy was based on a now-outdated staging snapshot. **Locked behavior:** the worker captures `staging.version` at the start of the agent loop and passes it as `expected_version` on the final `import_full_registry_to_staging` call. On version mismatch the call fails with `STALE_VERSION`; the job transitions to `failed` with `error_code = STALE_VERSION`, `details.expected_version` and `details.current_version` filled in. Operator's recourse: re-submit the job (the agent re-reads staging fresh). This is the safer default — preferable to silently clobbering concurrent edits the agent never saw. The test asserts exactly this outcome; a follow-up test asserts that re-submitting succeeds.
- *Job-stuck timeout.* Submit a job with a stub LLM that intentionally never finishes (returns the same tool call forever). Assert the worker transitions the job to `failed` with `error_code=WALL_CLOCK_TIMEOUT` within `INGESTION_JOB_WALL_CLOCK_TIMEOUT_S + 5s`, and that the job's `finished_at` is set.
- *Postgres disappears mid-promote.* Use testcontainers to pause the Postgres container at the start of `promote_staging_to_production`; resume after 10s. Assert the operation either (a) completed atomically (rare, race), or (b) returned a 5xx and the registries rows are in their pre-promote state. Never half-applied.
- *LLM provider error mid-step.* Stub LLM that returns `503 Service Unavailable` on step 30. Assert the agent loop captures the error, the job transitions to `failed` with `error_code=LLM_PROVIDER_ERROR`, and `details.driver_error` is recorded but DSN-redacted.
- *MCP client disconnects mid-`query_sql`.* Open an MCP client, submit a long-running `query_sql`, kill the client. Assert the server-side query is cancelled (Postgres / MySQL session terminated, connection returned to the pool), and the audit_log row records `outcome = "client_disconnected"`.

### 11.6 Real-LLM golden ingestion test (release-gated)

Stub-LLM tests in §16.10 verify the agent loop's plumbing. They cannot tell us whether real LLMs actually do a good job. This test fills that gap.

`tests/golden/test_real_llm_ingestion.py` — gated behind `@pytest.mark.live_llm`, only runs when the env var `RUN_LIVE_LLM_TESTS=1` is set, which is set on release-candidate runs but not on every CI commit. Costs real money per invocation.

Inputs (committed to `tests/fixtures/golden/`):
- `tests/fixtures/golden/logistics_ddl.sql` — same as the §11.4 fixture.
- `tests/fixtures/golden/logistics_glossary.md` — short domain notes ("Material codes follow MTL-NNNN format. Stations belong to a single warehouse. The MD_ prefix denotes master data; BO_ denotes business objects; BW_ denotes business warehouse").

Test runs the full ingestion pipeline against each provider/model in a configured matrix (e.g., `volcengine/doubao-pro-32k`, `openai/gpt-4o-mini`, `anthropic/claude-haiku-4-5`). Per-run assertions:

- Status reaches `imported` within `INGESTION_JOB_WALL_CLOCK_TIMEOUT_S`.
- Resulting staging registry contains ObjectTypes whose `api_name` includes at least the substrings `material`, `station`, `warehouse_location`, `delivery_task` (case-insensitive). Lets the agent pick its preferred naming as long as the major entities are recognized.
- At least one LinkType exists between any two of the recognized ObjectTypes.
- Validator passes (no `ERROR` findings).
- All `read_connection_id` fields are either empty or resolve. (We don't expect the agent to bind connections without being asked, but if it does, they must be valid.)
- `decisions_report` is non-empty and includes at least one `interpret-as-link` decision.

The matrix and per-model outputs are written to `tests/fixtures/golden/runs/<date>/<provider>-<model>.json` so historical regressions can be diffed across model versions. When a model is upgraded (e.g., Doubao bumps a minor version), this is the canary that tells us whether ingestion quality drifted.

Failure of a real-LLM test is informational by default — it's posted to the release notes for review, but doesn't block CI. The exception is when *every* configured provider fails the same way on the same fixture: that's promoted to a blocker (suggests a regression in our prompt or extractor, not in the model).

## 12. Deployment

- **Container image.** `docker/Dockerfile` — slim Python 3.12 base, dependencies installed via `uv`, non-root user, bind on `0.0.0.0:8080`.
- **Compose stack.** `docker/compose.yaml` services:
  - `app` — the platform process. Healthcheck hits `/healthz`. Depends on `postgres`.
  - `postgres` — Postgres 16, named volume for `/var/lib/postgresql/data`, healthcheck via `pg_isready`.
- **Environment variables** (documented in `.env.example`):
  - `ONTO_DATABASE_URL` — Postgres DSN for platform metadata.
  - `ONTO_SECRET_KEY` — Fernet key (44-char base64). Required.
  - `ONTO_BIND_HOST`, `ONTO_BIND_PORT` — defaults `0.0.0.0` / `8080`.
  - `ONTO_LOG_LEVEL` — default `info`.
  - `ONTO_QUERY_DEFAULT_MAX_ROWS`, `ONTO_QUERY_MAX_ROWS_CAP`, `ONTO_QUERY_DEFAULT_TIMEOUT_MS`, `ONTO_QUERY_TIMEOUT_MS_CAP` — `query_sql` envelope tuning.
- **Migrations** run on container start via `alembic upgrade head` in the entrypoint, before the FastAPI app boots.
- **Bootstrap admin token** is printed to container stdout on first run with the prefix `ADMIN BOOTSTRAP TOKEN:` so an operator can `docker compose logs app | grep BOOTSTRAP`. On subsequent starts (table non-empty), nothing is printed.
- **Operator script** `bin/onto-admin` — thin wrapper around `cli.py` for: re-issue bootstrap (after wiping `api_tokens`), rotate `ONTO_SECRET_KEY`, dump/restore registries to/from JSON, force-revoke all tokens.

## 13. Observability

- **Structured JSON logs** to stdout, one line per event. Fields: `ts`, `level`, `request_id`, `token_label`, `scope`, `tool`, `latency_ms`, `outcome`, `error_code`. Logs are ephemeral.
- **Health endpoints.**
  - `/healthz` — process up. Always 200 once the app has finished startup.
  - `/readyz` — DB reachable, all three `registries` rows present, `ONTO_SECRET_KEY` valid (decrypts a known canary). 503 otherwise.
- **Audit log** is the durable record. Every successful and failed dispatch produces one `audit_log` row. The future UI surfaces this; in V1 it's queryable via SQL.

## 14. Out of scope (call-outs)

These are excluded from V1. Each is independently addable later without disturbing this design's core abstractions:

- **Writeback** to bound DBs. Proto's `writeback_*` fields are accepted in stored definitions and validated for shape, but the runtime never executes writes against bound connections. Adding writeback is a security-sensitive change deserving its own spec (txn semantics, conflict handling, audit, scope changes).
- **`ActionType` execution.** Definitions are stored and validated; no runner.
- **Form-based entity editor in the UI.** V1 UI is browse + diff + ingest only; entity CRUD happens via MCP. Add later if MCP-from-Claude-IDE proves insufficient.
- **Admin views in the UI** (tokens, connections, audit log). Admin operations are MCP-only in V1.
- **Multi-tenant orgs, SSO, fine-grained per-row ACL, full version history, metrics/tracing endpoints, rate limiting, SSE/WebSocket push.**

## 15. Open questions

None blocking. The design has been walked through end-to-end with the user; proceed to the implementation plan via the writing-plans skill.

## 16. Sub-project 2 — File ingestion

### 16.1 Purpose

Operators upload a bundle of docx / pptx / xlsx / pdf / .sql files. An LLM-driven agent reads them, builds (or refines) a candidate `OntologyRegistry`, runs it through the validator, and writes it into staging via the same `import_full_registry_to_staging` tool that human / AI editors already use. The operator then reviews the result in staging using the existing tooling and promotes when ready.

The ingestion service does **not** introduce a parallel writing path; everything funnels through the §5.2 editor-scope tools.

### 16.2 LLM runtime — vendor-neutral

Per saved user preference, the LLM client must be vendor-neutral: any OpenAI-compatible or Anthropic-compatible endpoint must work (the user runs Volcengine + others). Implementation:

- **LiteLLM** as the provider abstraction. One `litellm.completion(...)` call works against OpenAI, Anthropic, Volcengine, DeepSeek, Aliyun Dashscope, OpenRouter, etc., and translates tool-call formats per provider.
- A **small in-house agent loop** (~150 lines, in `onto_platform/ingestion/agent.py`) drives tool-using turns: send messages + tool definitions, receive a response, dispatch any tool_calls in-process against the editor-scope tool handlers from §5.2, append tool results, loop. Stops on a final assistant message with no tool_calls or on a configurable step cap.
- Configuration knobs (`config.py`, env-tunable per deployment): `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MAX_STEPS` (default 50), `LLM_REQUEST_TIMEOUT_S` (per-call, default 120), `INGESTION_JOB_WALL_CLOCK_TIMEOUT_S` (whole-job ceiling, default 1800 = 30 min).
- Resource limits enforced at upload and submission time (env-tunable, defaults shown): `INGESTION_MAX_UPLOAD_BYTES = 25_000_000` (25 MB per file), `INGESTION_MAX_FILES_PER_JOB = 20`, `INGESTION_MAX_TOTAL_BYTES_PER_JOB = 100_000_000` (100 MB across all files in one job). Violations return `UPLOAD_TOO_LARGE` / `JOB_TOO_LARGE` (added to §16.9).

The agent's tool calls mutate an **in-memory working copy of the registry**, not the persisted staging row. The worker loads the current staging registry into a `WorkingRegistry` object (or starts from empty if `mode=replace`); the agent's tool dispatcher applies each call against that object only; on agent completion the worker validates the working copy and then submits the result through the regular `import_full_registry_to_staging` path with the job's `mode`.

This makes cancellation, step-cap exhaustion, and any agent failure cleanly safe: staging is untouched until the very last step, so there is no partial-write to undo. The agent's tool *shapes* mirror the §5.2 editor-scope tools (same names, same arg schemas) so the LLM sees a familiar surface, but the implementations live in `ingestion/working_ops.py` and operate on `WorkingRegistry` objects in memory.

### 16.3 Module layout (additions to §4.1)

```
onto_platform/
├── ingestion/
│   ├── extractors/
│   │   ├── __init__.py     # registry: extension -> extractor
│   │   ├── sql.py          # sqlglot-based DDL parser; emits {tables, columns, fks, comments}
│   │   ├── pdf.py          # pypdf -> per-page text + headings
│   │   ├── docx.py         # python-docx -> structured paragraphs/tables
│   │   ├── pptx.py         # python-pptx -> per-slide text + notes
│   │   └── xlsx.py         # openpyxl -> per-sheet headers + sample rows
│   ├── agent.py            # in-house tool-using agent loop over LiteLLM
│   ├── tools.py            # tool definitions exposed to the agent (mirrors editor scope §5.2)
│   ├── prompts.py          # system prompt (ported from .claude/commands/ontology-model.md)
│   ├── store.py            # CRUD on `ingestion_jobs` and `ingestion_uploads` tables
│   ├── workers.py          # asyncio task supervisor; concurrency cap; cancellation
│   └── http.py             # POST /admin/ingestion/uploads + jobs CRUD REST endpoints
```

### 16.4 Postgres schema additions

| Table | Columns | Notes |
|---|---|---|
| `ingestion_uploads` | `id` uuid PK; `job_id` nullable uuid (set when associated with a job); `filename`; `kind` ∈ {`sql`,`pdf`,`docx`,`pptx`,`xlsx`}; `size_bytes`; `sha256`; `path` text (relative path under `ONTO_INGESTION_DATA_DIR`); `created_at`; `created_by_token_id` | One row per uploaded file. Files on disk are deleted when the owning job reaches a terminal state (or on TTL if uploaded but never used in a job). |
| `ingestion_jobs` | `id` uuid PK; `mode` ∈ {`replace`,`merge`}; `instructions` text nullable; `status` ∈ {`queued`,`extracting`,`agent_running`,`validating`,`imported`,`failed`,`cancelled`}; `phase_message` text; `progress_pct` int 0–100; `decisions_report` jsonb nullable (filled on success); `staging_version_after` int nullable; `error_code` text nullable; `error_details` jsonb nullable; `created_at`; `created_by_token_id`; `started_at` nullable; `finished_at` nullable | The `decisions_report` jsonb captures `{decisions: [{kind: "interpret-as-link", source_table: "...", reason: "..."}], imported_entity_counts: {...}, validator_warnings: [...]}` so operators can audit what the agent chose. |

`ingestion_uploads.path` is relative to `ONTO_INGESTION_DATA_DIR` (default `var/ingestion`); files live under `{data_dir}/{job_id_or_orphan}/{upload_id}_{filename}`. Deletion at terminal state is idempotent.

### 16.5 File extractors

Each extractor returns a `ExtractedDocument(kind, source_filename, sections: list[Section])` where `Section` has a `heading` and `text` plus optional structured payload (e.g., for `.sql` the structured payload is the parsed table/column/FK list). The agent receives a single `extraction_bundle` system message that catalogues every extracted document by filename + kind + section headings, and the section bodies are placed in the user message in a documented order: `.sql` first (schema source), then `.docx`/`.pdf` (domain prose), then `.xlsx`/`.pptx` (auxiliary).

Extractor failures (corrupt file, unsupported format) are reported as `error_code = EXTRACTION_FAILED` with the offending filename in `error_details` and the job transitions to `failed` without ever calling the agent.

### 16.6 Agent loop

```python
async def run_agent(job: IngestionJob, bundle: ExtractionBundle) -> AgentResult:
    messages = [
        {"role": "system", "content": render_system_prompt(job)},
        {"role": "user", "content": render_user_message(bundle)},
    ]
    tools = build_tool_definitions()  # editor-scope tools, formatted for current provider
    for step in range(settings.llm_max_steps):
        resp = await litellm.acompletion(
            model=settings.llm_model,
            api_base=settings.llm_base_url,
            api_key=settings.llm_api_key,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            timeout=settings.llm_request_timeout_s,
        )
        msg = resp.choices[0].message
        messages.append(msg.model_dump())
        if not msg.tool_calls:
            return AgentResult(final_message=msg.content, steps=step + 1, decisions=collect_decisions())
        for call in msg.tool_calls:
            result = await dispatch_tool_call(call, job=job)  # in-process; same handlers as MCP
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
        await persist_phase(job, step, len(msg.tool_calls))
    raise StepCapExceeded(settings.llm_max_steps)
```

`dispatch_tool_call` mutates only the per-job `WorkingRegistry` in memory (see §16.2). It records each call — name, args summary, applied result, agent's stated reason from the message — into the job's `decisions_report` so the operator can later audit exactly what the agent did. The submitting token's scope is verified at job-submission time (must be ≥ editor); the worker re-checks the token's `revoked_at IS NULL` once at agent start and aborts with `UNAUTHORIZED_REVOKED` if revoked mid-flight.

### 16.7 Submission and lifecycle

**Step 1 — Upload files.** `POST /admin/ingestion/uploads` (multipart). Accepts one file per request; returns `{upload_id, kind, size_bytes, sha256}`. Reject unknown extensions. Token: `editor`.

For pure-MCP clients there's also `register_upload(filename, base64_content)` (admin scope, since base64-over-MCP is bandwidth-expensive and we want operators to use REST when possible).

**Step 2 — Submit job.**
- REST: `POST /admin/ingestion/jobs {upload_ids, mode, instructions?}` — token: `editor`.
- MCP: `submit_ingestion_job(upload_ids, mode, instructions?)` — scope: `editor`.

Returns `{job_id, status: "queued"}` immediately.

**Step 3 — Worker picks up the job.** `workers.py` keeps a bounded asyncio task pool (`ONTO_INGESTION_MAX_CONCURRENT`, default 2). State transitions:

```
queued → extracting → agent_running → validating → imported     (success)
                                  ↓
                                  failed     (any error)
                                  ↓
                                  cancelled  (operator cancel before agent finishes)
```

During `extracting`, the worker runs all extractors and assembles the bundle. During `agent_running`, the agent loop runs against the per-job `WorkingRegistry` in memory; staging is not touched yet. During `validating`, the worker runs the §7 validator against the working registry; failure → `failed` with `error_code = VALIDATION_FAILED` and `error_details.findings` (and staging is still unchanged). Success → call `import_full_registry_to_staging(working_registry, mode=job.mode)`, which itself re-validates inside its transaction; on success the job records `staging_version_after`.

**Step 4 — Polling.** `GET /admin/ingestion/jobs/{id}` and MCP `get_ingestion_job(job_id)` (editor scope) return the row with the live status. The UI polls every 2s while status is in a non-terminal state.

**Step 5 — Cancellation.** `POST /admin/ingestion/jobs/{id}:cancel` and MCP `cancel_ingestion_job(job_id)` (editor — operator can cancel their own jobs; admin can cancel anyone's). Cancellation is cooperative: the worker checks a flag between agent steps and aborts cleanly if set. Because the agent only mutates the in-memory working copy, cancellation requires no rollback — staging is unchanged regardless of where in the pipeline the cancellation lands.

### 16.8 Editor-scope MCP tools added in S2

| Tool | Purpose |
|---|---|
| `submit_ingestion_job(upload_ids, mode, instructions?)` | Kick off a job. Returns `{job_id}`. Files must already be uploaded via REST or `register_upload`. |
| `get_ingestion_job(job_id)` | Status + decisions report + diff summary. |
| `list_ingestion_jobs(status?, limit?, before?)` | Paginated listing. |
| `cancel_ingestion_job(job_id)` | Cooperative cancellation. |

Plus admin-scope:

| Tool | Purpose |
|---|---|
| `register_upload(filename, base64_content)` | MCP-only file upload. Limited to small files (configurable, default 5MB cap) to discourage MCP transport abuse. |
| `delete_orphan_uploads(older_than_minutes)` | Garbage-collect uploads never used by a job. |

### 16.9 Errors specific to S2

Adds these codes to §10:

| Code | Meaning |
|---|---|
| `UPLOAD_NOT_FOUND` | An `upload_id` referenced at submission doesn't exist or is already attached to another job. |
| `UPLOAD_KIND_UNSUPPORTED` | The uploader sent an extension that has no extractor. |
| `EXTRACTION_FAILED` | At least one file failed to parse; `details.failed_files` lists `{filename, reason}`. |
| `LLM_PROVIDER_ERROR` | The LiteLLM call failed (network, auth, quota); `details.driver_error`. |
| `STEP_CAP_EXCEEDED` | The agent exceeded `LLM_MAX_STEPS` without producing a final answer. Staging is unchanged (the working copy is discarded). |
| `WALL_CLOCK_TIMEOUT` | The job exceeded `INGESTION_JOB_WALL_CLOCK_TIMEOUT_S`. Worker's outer guard fired and the agent task was cancelled. Staging is unchanged. |
| `UPLOAD_TOO_LARGE` | A single file exceeded `INGESTION_MAX_UPLOAD_BYTES`. Returned at upload time. |
| `JOB_TOO_LARGE` | Submission exceeded `INGESTION_MAX_FILES_PER_JOB` or `INGESTION_MAX_TOTAL_BYTES_PER_JOB`. Returned at submit time. |
| `UNAUTHORIZED_REVOKED` | The job's submitting token was revoked between submission and agent start; the worker aborted before doing any LLM work. |
| `JOB_NOT_FOUND` / `JOB_TERMINAL` | Self-explanatory — `cancel_ingestion_job` against a job that's already finished. |

### 16.10 Testing additions

- **Unit tests** for each extractor (`tests/unit/test_extractors_*.py`) — small synthetic input files of each format checked into `tests/fixtures/extractors/`. Assert structural extraction shape; do NOT compare against full text byte-for-byte (extractor library upgrades are allowed to slightly reformat text). Include a deliberately-corrupt fixture per type to assert clean `EXTRACTION_FAILED`.
- **Unit tests** for the agent loop using a stub LLM client (`StubLiteLLM`) that scripts a fixed sequence of tool calls. Coverage:
  - Happy-path tool dispatching (assert each scripted call applied to the working registry in order).
  - `decisions_report` capture (assert each call surfaces in the report with the agent's stated reason).
  - `STEP_CAP_EXCEEDED`: stub returns a tool call indefinitely; assert the loop terminates at `LLM_MAX_STEPS` and `error_code` is correct.
  - `WALL_CLOCK_TIMEOUT`: stub returns slowly; assert the worker's wall-clock guard fires.
  - Cancellation responsiveness: stub stalls; cancellation flag set externally; assert the next dispatch boundary aborts within 1s.
  - `LLM_PROVIDER_ERROR`: stub raises a transport error; assert the loop captures it and the worker records DSN-redacted `details.driver_error`.
  - Malformed tool-call args: stub emits a tool call with a missing required arg; assert the loop returns a tool error to the model and continues (does not crash). Repeat for an unknown tool name.
  - Working-registry isolation: assert no DB write to the `registries` table happens during the agent loop — only at the final `import_full_registry_to_staging` boundary.
- **Provider compat unit tests.** Cover the small set of provider-specific quirks the in-house code touches directly (tool-call schema for OpenAI vs. Anthropic vs. Doubao). Stub LiteLLM at the boundary by patching `litellm.acompletion`. Assert our code hands LiteLLM the right `tools=` payload shape per provider and correctly parses each provider's `tool_calls` response shape. (The earlier draft used `pytest-httpserver` to fake a real HTTP exchange; that turned out to test LiteLLM's HTTP behavior more than ours, with low signal. Replaced.)
- **Real-LLM golden tests.** Provider/model matrix lives in §11.6; release-gated, not in CI.
- **End-to-end ingestion test** added to §11.4: uploads `tests/fixtures/sql/logistics_ddl.sql` plus a small Markdown "domain notes" file (`tests/fixtures/docs/logistics_glossary.md`), submits a job with `mode=replace`, polls until terminal, asserts the resulting staging registry contains the expected ObjectTypes (`Material`, `Station`, …) and that the `decisions_report` is non-empty. Uses the stub LLM with a scripted plan that mirrors what a real agent would do — keeps the test deterministic. The same fixture is what §11.6 hits with real providers.
- **Resource-limit tests.** Upload a file at `INGESTION_MAX_UPLOAD_BYTES + 1` → `UPLOAD_TOO_LARGE`. Submit a job with `INGESTION_MAX_FILES_PER_JOB + 1` uploads → `JOB_TOO_LARGE`. Submit a job whose total bytes exceed `INGESTION_MAX_TOTAL_BYTES_PER_JOB` → `JOB_TOO_LARGE`. Assert correct error codes and that no `ingestion_jobs` row is created on the failing submissions.

## 17. Sub-project 3 — Web UI

### 17.1 Purpose and scope

A browser-based operator console for the day-to-day "what does my ontology look like and is staging ready to promote" loop, plus the file-ingestion experience (drag/drop, watch the job, see the diff).

V1 explicitly excludes a form-based entity editor and the admin views (tokens / connections / audit log). Entity edits and admin operations happen via MCP from a Claude IDE. This keeps the UI small enough to actually ship.

### 17.2 Stack

- **React 18 + Vite + TypeScript + TailwindCSS.**
- UI primitives: **shadcn/ui** (Radix under the hood) — cheap, reskinnable, no heavy component library lock-in.
- Routing: **react-router** (data-router style, matches our route-loader pattern).
- Server state: **TanStack Query** for fetches/cache/polling (built-in interval-based refetch is exactly what the ingestion-job poll needs).
- Forms: **react-hook-form** + **zod** for the few forms we ship (login, ingestion submit). Schemas mirror the server's pydantic models.
- Graph viz: **react-flow** + **@dagrejs/dagre** for auto-layout. Custom node renderers per entity kind.
- Build target: a single `dist/` directory served by FastAPI as static files. No separate Node server in production.

### 17.3 Module layout (additions)

```
ui/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
├── index.html
├── src/
│   ├── main.tsx               # react-router setup, query client, theme provider
│   ├── api/
│   │   ├── client.ts          # fetch wrapper, credentials: 'include' for session cookie
│   │   ├── ontology.ts        # typed wrappers for read tools
│   │   ├── lifecycle.ts       # promote/revert/undo
│   │   └── ingestion.ts       # uploads + jobs
│   ├── auth/
│   │   ├── login.tsx          # paste-token form -> POST /admin/login
│   │   ├── session.ts         # session-cookie status, scope context
│   │   └── route-guard.tsx    # protected-route HOC
│   ├── views/
│   │   ├── dashboard/
│   │   ├── ontology-browser/
│   │   ├── graph/
│   │   ├── diff/
│   │   └── ingestion/
│   ├── components/
│   │   ├── entity-detail-panel.tsx
│   │   ├── env-switcher.tsx   # staging | production toggle
│   │   ├── decisions-report.tsx
│   │   └── ...
│   └── lib/
│       ├── proto-types.ts     # generated TS types from proto/ via protobuf-ts
│       └── colors.ts          # consistent kind -> color map for nodes/badges
└── tests/
    └── e2e/                   # Playwright end-to-end UI tests
```

The platform's backend serves the built `ui/dist/` from `/`; API requests live under `/api/*` and `/mcp`. Vite dev server proxies API requests during development.

### 17.4 Auth bridge

New `/admin/login` REST endpoint:

- `POST /admin/login {token}` → server hashes & verifies the token row → on success creates a row in a new Postgres table `ui_sessions(id uuid PK, token_id uuid FK, scope, created_at, expires_at)` with `expires_at = now() + ONTO_UI_SESSION_TTL` (default 12h) and returns it as an `httpOnly SameSite=Strict` cookie named `onto_session`. The `Secure` attribute is set when `ONTO_UI_COOKIE_SECURE=true` (default in production); local dev runs over plain HTTP and disables the flag via env so cookies actually persist.
- `POST /admin/logout` → revokes the session row, clears the cookie.
- All `/api/*` and `/admin/*` (except `/admin/login` itself) accept either a session cookie OR a bearer token. Token bearer is what MCP uses; session cookie is what the UI uses. The middleware (§6.3) is extended to recognize either.
- `GET /api/whoami` mirrors the MCP `whoami` tool — returns `{token_label, scope, server_version}` derived from whichever credential the request carried.

The UI's "login" page is just a paste-token form. Tokens are minted via MCP from a Claude IDE (since admin views are MCP-only in V1). This is bootstrap-friendly because the operator's first move when setting up the platform is opening Claude IDE with the bootstrap admin token anyway — they can mint themselves a UI session token there.

### 17.5 Views

#### 17.5.1 Dashboard (route `/`)

Two-column landing card.

- **Environment summary** — for each of `staging` and `production`: entity counts per kind, current `version` integer, last-update timestamp, last commit message (production only), `previous_production` slot occupied? badge.
- **Connections health** — list of registered connections with green/red status from `last_probe_ok_at`. Click a row to see the full connection details panel (DSN still redacted).
- **Recent activity** — last 20 audit-log entries (read-only; filtered to non-sensitive tools) — gives operators a quick "did anything happen overnight?" view without needing to open a terminal.
- **Live ingestion jobs** — banner near the top if any job is in a non-terminal state, with a link to the Ingestion view.

#### 17.5.2 Ontology browser (route `/browse/:env`)

Sidebar with five collapsible groups (one per entity kind), each listing entities by `display_name` with a search box that filters by `api_name` and `display_name`. Selecting an entity opens a right-pane detail view: pretty-printed JSON of the definition, with cross-references rendered as clickable links to the referenced entities (via `find_by_api_name` / `get_entity` round-trips).

The env switcher (top-right) toggles between `staging` and `production` — same URL, different `:env` segment. Sticky in the URL so links can be shared.

#### 17.5.3 Graph view (route `/graph/:env`)

react-flow canvas with dagre auto-layout. Nodes are entities (one shape per kind, color-coded; restricted-sensitivity properties get a small lock badge). Edges are the seven ontology relationships from `ONTOLOGY.md`:

- `BASED_ON` — PropertyType → SharedPropertyType
- `BELONGS_TO` — PropertyType → ObjectType / LinkType
- `IMPLEMENTS` — ObjectType / LinkType → InterfaceType
- `REQUIRES` — InterfaceType → SharedPropertyType
- `EXTENDS` — InterfaceType → InterfaceType
- `CONNECTS` — LinkType ↔ ObjectType (both ends rendered)
- `OPERATES_ON` — ActionType → ObjectType / LinkType / InterfaceType

Edge style differs per relationship (dotted for inheritance, solid for connection, dashed for operation). Toolbar: filter by entity kind (toggle chips), search-and-zoom-to entity, switch to "expand from selected" mode that hides anything not within N hops of the selected node. Click a node to open the same detail panel as the browser view.

For larger registries (>200 entities), default view is a clustered layout where ObjectTypes drawn near their bound connection's "swim lane" — this surfaces the data-source coupling visually.

#### 17.5.4 Diff view (route `/diff`)

Side-by-side staging vs production. Three lists: **Added** (in staging, not in production), **Removed** (in production, not in staging), **Modified** (RID present in both, JSON differs). Each entry expands to a syntactically-aware JSON diff panel.

A green **Promote** button at the bottom (admin scope only — disabled with a tooltip if the session is editor-scope) opens a confirmation modal that requires typing `PROMOTE` plus an optional commit message, then calls `promote_staging_to_production`. A red **Revert** button discards staging — same confirmation pattern (`REVERT`).

If `previous_production` is occupied, an `Undo last promote` link appears in the modal-less header.

#### 17.5.5 Ingestion (route `/ingest`)

Two panes.

- **New job** — drag/drop area accepting docx/pptx/xlsx/pdf/sql; uploaded files appear as chips with size + extracted-kind labels and a remove button. Below: mode picker (`merge` default, `replace` with a warning tooltip), free-text instructions textarea, **Submit** button. Submission calls `POST /admin/ingestion/uploads` per file (in parallel) then `POST /admin/ingestion/jobs`. UI navigates to the job detail view.
- **Jobs list** — table of recent jobs (last 50, paginate older). Columns: id, mode, status badge, phase, progress, created at, owner. Auto-refreshes every 5s while any job is non-terminal; switches to manual refresh once all are terminal.

Job detail view (`/ingest/:job_id`):

- Status header with phase + progress bar; polls `GET /api/ingestion/jobs/:id` every 2s while non-terminal.
- **Decisions report** — once available, render the agent's structured `decisions_report` as a tree (group by decision kind: `interpret-as-link`, `interpret-as-object`, `mark-as-virtual`, `attach-asset-mapping`, etc.). Each entry expands to show the source-table or source-document context the agent used.
- **Result diff** — same component as the diff view, but pre-filtered to "what this job changed in staging." On `imported` status, this is the operator's review surface; from here they can navigate to the full diff view to promote.
- **Error panel** — on `failed` status: error code, error details, links to the offending uploads. **Cancel** button while non-terminal (calls `cancel_ingestion_job`). **Retry** button when failed (re-uses the same `upload_ids`, opens the New Job pane pre-populated).

### 17.6 REST API additions for the UI

Beyond `/admin/login`, `/admin/logout`, `/admin/ingestion/*` already covered:

| Endpoint | Purpose |
|---|---|
| `GET /api/whoami` | Session/token introspection. |
| `GET /api/registries/:env/summary` | Counts + version + updated_at; cheap dashboard fetch. |
| `GET /api/registries/:env/full` | Full registry payload (used by graph view). |
| `GET /api/registries/:env/entities/:kind` | Per-kind listing for the browser sidebar. |
| `GET /api/registries/:env/entities/:rid` | One entity. |
| `GET /api/registries/diff` | Computed diff staging vs production. |
| `GET /api/connections` | List connections + probe status (DSN redacted). |
| `GET /api/audit-log/recent?limit=` | Recent entries for the dashboard's activity feed (max 50, no admin-grade filters in V1). Full filterable audit access stays MCP-only. |
| `POST /api/registries/promote {commit_message}` | Same as MCP tool. |
| `POST /api/registries/revert` | Same as MCP tool. |
| `POST /api/registries/undo-promote` | Same as MCP tool. |

All `/api/*` endpoints accept either a session cookie OR a bearer token. The handlers are thin wrappers around the same Python functions that back the MCP tools — there is exactly one source of truth per operation.

### 17.7 Deployment delta

- The `app` Docker image runs a Vite build during image build (`npm ci && npm run build` in a builder stage) and copies `ui/dist/` into the final image at `/srv/ui/dist`. FastAPI mounts it via `app.mount("/", StaticFiles(directory="/srv/ui/dist", html=True))` after registering all `/api/*`, `/admin/*`, and `/mcp` routes (so route precedence is correct).
- Dev mode (`make dev`) runs Vite (`npm run dev`) on port 5173 with a proxy config for `/api`, `/admin`, `/mcp` → FastAPI on 8080.
- New env var: `ONTO_UI_SESSION_TTL` (seconds, default 43200 = 12h).

### 17.8 Testing additions

- **Component tests** (Vitest + @testing-library/react) — for the diff renderer, the decisions-report tree, the env-switcher, the entity-detail-panel link resolution. Mocks the API client.
- **End-to-end UI tests** (Playwright, in `ui/tests/e2e/`) — driven against the same testcontainers stack from §11. Scenarios:
  1. *Login flow* — paste a freshly minted editor token, see the dashboard, log out, paste a revoked token, see error.
  2. *Session expiry* — log in, force-expire the `ui_sessions` row server-side (or set `ONTO_UI_SESSION_TTL=2` for the test), make a protected request after expiry, assert redirect to login with a "session expired" notice.
  3. *Browse + graph* — load the seeded logistics ontology, verify all 4 ObjectTypes appear in the sidebar; switch to graph view, verify the dagre layout produces no overlapping nodes for that fixture (snapshot test on node positions); click a node, see its detail panel.
  4. *Ingestion happy path* — drag in `logistics_ddl.sql` + `logistics_glossary.md`, submit with `mode=replace`, watch the job progress through phases (using the same stub LLM from §16.10), verify the decisions report renders, navigate to the diff view, promote (with admin token), verify production updates.
  5. *Ingestion failure* — drag in a deliberately corrupt PDF, submit, verify the failed-job UI shows `EXTRACTION_FAILED` with the offending filename.
  6. *Diff/promote forbidden* — log in with editor token, navigate to diff, verify Promote button is disabled with a permission tooltip.
  7. *UI mediation of masking.* Open the ontology browser to the `cost_price` property, confirm its detail panel renders the sensitivity badge. Trigger a `query_sql` from a small "preview rows" affordance in the entity-detail panel and assert the rendered table shows `***` in the `cost_price` column — i.e., the UI doesn't strip masking when displaying server output.
- **Accessibility tests.** Each Playwright e2e scenario above runs `axe-core` against the loaded page and asserts zero `serious`/`critical` violations. Cheap insurance against regressions in keyboard navigation, contrast, and ARIA labelling.

Playwright tests run in CI but are gated behind a `make e2e-ui` target so they don't slow normal `make test` runs (browser startup is heavy). The same green/red gate as the backend e2e suite.


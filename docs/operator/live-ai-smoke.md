# Live AI Smoke Test (§11.4)

This runbook is the human-in-the-loop check that the MCP tool surface
actually feels right to a real AI client. It is **not run in CI** — it
hits a real Claude IDE (or any MCP-aware IDE) and depends on the
operator visually verifying the AI's responses.

## Stack

`make e2e-ai` boots:

- A Postgres container (platform metadata) on a random port.
- A MySQL container seeded with `tests/fixtures/sql/logistics_ddl.sql`,
  `tests/fixtures/sql/logistics_seed.sql`, and `tests/fixtures/sql/scheduling.sql`.
- The platform process via `uvicorn` on port 8080.

The script then:

1. Resets `api_tokens` and registers the MySQL container as a connection.
2. Loads `tests/fixtures/ontology/logistics_registry.json` into staging
   and promotes it to production.
3. Mints a fresh `editor`-scope token, then a fresh `read`-scope token,
   and prints both.
4. Prints an `mcp.json` snippet you paste into Claude Code's MCP config
   (via `claude mcp add` or by editing `~/.claude/mcp.json`).

## Canonical prompts

Run each prompt against Claude Code and record the observed behavior.
A prompt **passes** if the AI takes the listed tool call(s) without
extensive flailing and the response is sensible. Mark observed values
under each "Observed:" header.

### 1. "What object types are in the production ontology?"

- **Expected tool calls:** `list_object_types({env: 'production'})`
- **Expected response shape:** A clean enumeration of the seeded
  `material`, `station`, `warehouse_location`, `delivery_task` types.

Observed: _______

### 2. "Find the 5 materials with the lowest stock."

- **Expected tool calls:** `describe_bound_asset` for `material`
  (and for `BW_STOCK_LEDGER` if the AI inspects the link), then
  `query_sql` joining `BW_STOCK_LEDGER` and `MD_MATERIAL`.
- **Expected response:** A table including the masked `PLAN_PRICE`
  column shown as `***`.

Observed: _______

### 3. "Show me delivery tasks that are still in progress."

- **Expected tool calls:** `describe_bound_asset` for `delivery_task`,
  then `query_sql` filtering `BO_DELIVERY_TASK_DETAIL` by status.
- **Expected response:** Rows with the seeded "IN_PROGRESS" tasks.

Observed: _______

### 4. "Add a new ObjectType called Pilot with a `name` property."

- **Expected tool calls:** `put_shared_property_type` (for `name` if
  not already present) → `put_object_type` (with `Pilot`) → optional
  `validate_staging`.
- **Expected response:** Reports the new staging version, no validator
  warnings.

Observed: _______

### 5. "Now promote staging to production."

- **Editor token only:** Expected `promote_staging_to_production` →
  `FORBIDDEN`. The AI should report the error gracefully and ask the
  operator for an admin token.
- **Admin token re-paste:** Expected success.

Observed: _______

### 6. "Drop the `daily_plan` table."

- **Expected tool calls:** `query_sql` attempt with `DROP TABLE`.
- **Expected response:** `SQL_REJECTED` error returned cleanly; the
  AI should report the rejection without retrying.

Observed: _______

## Capture

The IDE's MCP transcript (tool calls + arguments + responses) is
saved to `docs/operator/live-ai-smoke-runs/<date>.json` so historic
runs can be diffed. Reviewers compare against the previous run to
spot regressions in tool-selection behaviour or argument shapes.

## When this fails

The most common failures and what they mean:

- *AI keeps calling `list_object_types` repeatedly without ever calling
  `describe_bound_asset`* — tool descriptions are unclear about the
  data-flow handoff. Tighten the docstring.
- *AI passes the connection's label as `connection_id`* — argument
  schema needs to specify "uuid" format.
- *AI flails after `SQL_REJECTED`* — error message is unclear; consider
  adding more guidance in the response.

# Onto Platform UI Redesign — Chat-Driven Ingestion + Simplified Nav (zh-CN)

**Date:** 2026-04-28
**Status:** Approved (brainstorm complete; pending implementation plan)
**Owner:** narcy188
**Supersedes:** Sections of the existing UI/ingestion-page experience documented in `docs/superpowers/specs/2026-04-25-ontology-platform-backbone-design.md` and the implementation in `ui/src/views/ingestion/`.

## Goal

Replace the form-based ingestion page with a chat-driven experience, simplify the navigation to three items, default the UI to Simplified Chinese, and modernize the visual design — without breaking any MCP-facing surface, since MCP is the primary consumer of the platform.

## Decisions Locked In During Brainstorming

| # | Decision | Choice |
|---|---|---|
| 1 | Chat session lifetime | **Per-batch session.** Each conversation is self-contained around one batch of files. |
| 2 | Save / Cancel semantics | **Per-turn atomic commits + pre-session snapshot.** Each turn the agent mutates an in-memory WorkingRegistry; at turn end, `import_into_registry` writes the whole turn's mutations atomically to staging. Save just closes the session. Cancel restores the pre-session staging snapshot taken at session creation. (Original spec said "direct mutations per tool call"; revised after reading the existing agent — see Architecture.) |
| 3 | Agent autonomy per turn | **Fully autonomous.** Agent runs all needed tool calls in one turn; user reviews via the live graph after. No per-call approval prompts. |
| 4 | Live update mechanism | **SSE for agent stream; React Query refetch on turn boundaries.** Within a turn, the agent's tool calls stream over SSE for chat-pane progress. The staging graph refetches once on `turn_complete` (not 1.5 s polling — staging doesn't actually change mid-turn because the agent mutates an in-memory WorkingRegistry that only commits at turn end). |
| 5 | Promote / Revert location | **Toolbar buttons on the staging tab of Graph and Browser**, not a separate page. The existing diff modal opens from those buttons. |
| 6 | Past-session history | **Ephemeral.** No history. Save/Cancel cascade-deletes session + messages + journal. |
| 7 | i18n approach | **Hardcoded `zh-CN`.** No `react-i18next`, no locale JSON. Single-language UI. |
| 8 | Backend implementation strategy | **Wrap the existing ingestion-job pipeline.** `run_agent` / `run_one_job` stay intact. Add a `ChatSession` orchestrator that creates one ingestion job per chat turn. |

## Out of Scope

- Multi-user collaboration on a single session (one user per session).
- Localization beyond `zh-CN` (no English locale shipped).
- Audit log / session history UI.
- Persistent chat replay or transcript export.
- Real-time multi-user co-editing of staging.
- Per-tool-call approval workflow (we picked autonomous).
- Refactoring the existing MCP tool surface — kept untouched.

## Glossary

- **Chat session** — a single user's in-progress chat about one batch of files. Persists across page reloads (via `session_id` in `localStorage`) but is destroyed on Save or Cancel.
- **Turn** — one user message and the agent's autonomous response, including all tool calls it made. Streamed over SSE.
- **Pre-session snapshot** — a JSONB copy of the staging registry as of `chat_sessions.created_at`. Captured once at session creation, used as the rollback target on Cancel.
- **Live graph** — the right-pane ReactFlow rendering of the current staging registry. Refetches once per turn on `turn_complete` (no fast polling — staging only changes at turn boundaries).

## Architecture

```
                 ┌──────────────┐
                 │  MCP clients │ (Claude Code, etc — primary use case)
                 └──────┬───────┘
                        │ JSON-RPC
                        ▼
        ┌──────────────────────────────────┐
        │  FastAPI app (one process, :80)  │
        │ ┌──────────────┐ ┌─────────────┐ │
        │ │  MCP router  │ │  UI routes  │ │
        │ │  /mcp        │ │  /chat/...  │ │
        │ └──────┬───────┘ └──────┬──────┘ │
        │        │   share        │        │
        │        ▼                ▼        │
        │  ┌─────────────────────────┐    │
        │  │  Existing MCP tools     │    │
        │  │  (put_*, delete_*, …)   │    │
        │  └─────────────────────────┘    │
        │        ▲                        │
        │        │ tool calls             │
        │  ┌─────┴────────────────────┐  │
        │  │ Agent loop               │  │
        │  │ (run_agent in workers.py │  │
        │  │  — kept intact)          │  │
        │  └──────────────────────────┘  │
        │        ▲                        │
        │  ┌─────┴──────────┐              │
        │  │ ChatSession    │  NEW: thin shell over
        │  │ orchestrator   │  run_one_job that also
        │  │ (chat/...)     │  streams tool calls via SSE
        │  └────────────────┘
        └──────────────────────────────────┘
                        │
                        ▼
                 ┌─────────────┐
                 │  Postgres   │  + new tables: chat_sessions,
                 │             │    chat_messages, session_journal
                 └─────────────┘
                        │
        ┌───────────────┴────────────────┐
        ▼                                ▼
  Existing UI routes                Existing UI routes
  /graph/:env, /browse/:env         (now zh-CN, modern visual)
  + toolbar Promote/Revert
```

**Invariants:**

1. MCP tool surface is unchanged. Signatures, semantics, and error codes preserved.
2. `run_agent` and `run_one_job` are not modified, only wrapped. The chat path injects a journaling tool dispatcher; non-chat (pure-MCP) callers do not journal.
3. The live graph component does not know about chat sessions — it just polls `get_registry`. The chat page tells it whether to poll fast or slow.
4. SSE is a new endpoint (`GET /chat/sessions/:id/stream`); existing endpoints are not retrofitted with streaming.
5. Database migrations are additive only; nothing existing is dropped or altered.

## Backend

### New tables (one Alembic migration, additive)

```sql
CREATE TABLE chat_sessions (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  token_id               uuid NOT NULL,                                  -- which API token started it (FK to api_tokens.id)
  status                 text NOT NULL CHECK (status IN ('active','saving','cancelling')),
  pre_session_registry   jsonb NOT NULL,                                 -- snapshot of staging at session creation
  pre_session_version    int   NOT NULL,                                 -- staging registry version at session creation (for optimistic concurrency)
  created_at             timestamptz NOT NULL DEFAULT now(),
  last_turn_at           timestamptz                                     -- updated on each turn for the orphan sweep
);

CREATE TABLE chat_messages (
  id           bigserial PRIMARY KEY,
  session_id   uuid NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  turn_index   int  NOT NULL,
  role         text NOT NULL CHECK (role IN ('user','assistant','tool_call','tool_result')),
  content      jsonb NOT NULL,                                  -- shape depends on role; see below
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX chat_messages_session_idx ON chat_messages (session_id, id);
```

`session_journal` (proposed in earlier draft) is dropped — superseded by the `pre_session_registry` column. The pre-session snapshot is the only undo target we need because the existing agent commits one staging version per turn (atomic via `rstore.save(...)`); we don't need fine-grained per-tool-call undo. The Alembic migration also adds `chat_session_id uuid NULL REFERENCES chat_sessions(id)` to `ingestion_jobs` so each turn's job is associated with its session for diagnostics.

`chat_messages.content` shapes by role:

- `user` → `{ "text": "...", "upload_ids": ["..."] }`
- `assistant` → `{ "text": "..." }`
- `tool_call` → `{ "name": "put_object_type", "args": {...}, "sequence": int }`
- `tool_result` → `{ "sequence": int, "status": "ok"|"error", "summary": "...", "error": null|{...} }`

`status` lifecycle: `active` (default) → `saving` (briefly during `POST /save`) or `cancelling` (briefly during `POST /cancel`) → row deleted (cascade). The transient states exist so a crash-during-save/cancel is recoverable.

`turn_index` starts at 0 and increments per user message. All four roles can share the same turn_index (`tool_call`, `tool_result`, `assistant` all belong to the same turn as the `user` message that triggered them).

### New HTTP endpoints

All under `/chat/*`, all require `editor` scope (matches existing ingestion endpoints), all return JSON unless noted.

| Method | Path | Purpose | Notes |
|---|---|---|---|
| `POST` | `/chat/sessions` | Start a new session | Returns `{ session_id }`. Does *not* tie to a previous session. |
| `GET`  | `/chat/sessions/{id}` | Resume an existing session | Returns `{ session_id, status, messages: [...] }` for client to re-hydrate. 404 if dropped. |
| `POST` | `/chat/sessions/{id}/uploads` | Upload one file | Multipart. Thin proxy over existing `/admin/ingestion/uploads`. Returns `{ upload_id }`. |
| `POST` | `/chat/sessions/{id}/turns` | Submit user message + upload_ids | Body: `{ message: string, upload_ids: string[] }`. Creates an `ingestion_jobs` row (existing pipeline) tagged with `chat_session_id`, returns `{ turn_id }`, kicks off `run_one_job` in the background. Refused with 409 if a turn is already running on this session. |
| `GET`  | `/chat/sessions/{id}/stream?turn_id=X` | SSE stream of agent events | `text/event-stream`. See "SSE event types" below. Multiple consumers OK (fan-out via in-process `asyncio.Queue`). |
| `POST` | `/chat/sessions/{id}/save`   | End session, keep mutations | 409 if a turn is in flight. Sets status=`saving`, cascade-deletes session row. Returns 204. |
| `POST` | `/chat/sessions/{id}/cancel` | End session, replay journal | 409 if a turn is in flight. Sets status=`cancelling`, replays journal in reverse, cascade-deletes session row. Returns 204 on success or 500 with details if replay fails (session left in `cancelling` for operator inspection). |

All `/chat/*` endpoints also accept the `onto_session` cookie (UI-friendly), per the existing `require_scope_via_cookie_or_bearer` dependency. Pure-MCP clients can also drive a chat session via Bearer token if they want to (uncommon, but supported).

### SSE event types (`/chat/sessions/{id}/stream?turn_id=X`)

Each event is a single JSON object on a `data:` line. The stream closes once `turn_complete` or `turn_error` is sent.

- `agent_step_start` — `{ "step_index": int }`
- `tool_call` — `{ "sequence": int, "name": "put_object_type", "args": {...} }` — emitted *before* the tool runs
- `tool_result` — `{ "sequence": int, "status": "ok"|"error", "summary": "string", "error": null|{...} }` — emitted *after* the tool finishes
- `assistant_message` — `{ "content": "string", "partial": bool }` — partial=true for streaming chunks, false for the final consolidated message
- `turn_complete` — `{ "tool_calls_made": int }`
- `turn_error` — `{ "kind": "timeout"|"llm_error"|"tool_error"|"unknown", "message": "string" }`

Heartbeat: send `event: heartbeat\ndata: {"ts": <iso8601>}\n\n` every 15 s while idle so the connection isn't closed by intermediate proxies.

### Snapshot capture & rollback mechanism

The existing agent (`onto_platform/ingestion/agent.py:run_agent`) does not directly mutate staging; it accumulates changes in an in-memory `WorkingRegistry`. After the agent finishes, `import_into_registry` reconciles the WorkingRegistry against the prior staging snapshot, and `rstore.save(env=staging, new_reg, expected_version=...)` writes the resulting registry as a single new staging version (atomic, optimistically-concurrent). Each turn produces exactly one staging version bump.

Therefore there is no per-tool-call mutation to journal. Instead:

- **At session creation:** load the current staging snapshot via `rstore.load(s, Env.staging)`, persist it into `chat_sessions.pre_session_registry` along with `pre_session_version`. This is the only "before" state we need to remember.
- **Per turn:** the existing pipeline runs unchanged; staging gains one new version per successful turn.
- **On Cancel:** call `rstore.save(env=Env.staging, registry=pre_session_registry, expected_version=<current staging version>, token_label="chat-cancel")`. This commits the pre-session registry as a fresh staging version (the current registry's content is preserved in `previous_production` rotation history per the existing lifecycle, so it's not gone — the operator could `revert_staging_to_production` or replay an earlier ingestion if needed).
- **On Save:** just delete the session row. The mutations that landed during the session stay in staging.

If staging was changed by another caller between session start and Cancel (different `expected_version`), the rollback raises `StaleVersionError`. We surface that as a 409 to the UI: "暂存区已被其他操作修改，无法回退（请检查并手动清理）". The operator can then use the existing tools to repair.

Because the pre-session snapshot is captured *outside* the agent's tool path, there is no journaling decorator and no instrumentation of `run_agent` or `dispatch_agent_call`. The chat code path is purely an orchestrator wrapper around the existing run-one-job worker.

### Orphan recovery

On FastAPI app start (`bootstrap.py`, after the existing admin-token bootstrap):

1. Query `SELECT id FROM chat_sessions WHERE status = 'active' AND (last_turn_at < now() - interval '30 minutes' OR last_turn_at IS NULL AND created_at < now() - interval '30 minutes')`.
2. For each, attempt the same rollback logic as Cancel (restore `pre_session_registry`). Mark `status='cancelling'`. Log a `WARN` with the count and the duration of each abandoned session.
3. On rollback success, cascade-delete the row. On `StaleVersionError`, leave the row in `cancelling` and emit a `WARN` with operator-actionable detail.

Note that an abandoned session has at most one extra staging version compared to its pre-session snapshot (per-turn atomic commit), so rollback is "subtract one or more turns' worth of mutations". The blast radius of an abandoned chat is small.

### Concurrency

- One in-flight turn per session, enforced by an in-memory `running_turns: dict[session_id, turn_id]` registry. `POST /turns` returns 409 if `session_id` is in the registry. The registry is the source of truth while the process is alive; on app restart, the orphan-recovery sweep handles any sessions left in `active` state.
- Multiple browser tabs on the same session are allowed; both subscribe to the SSE fan-out queue. Both have their input fields disabled while a turn runs (the resumption GET tells them).
- The backend allows up to `chat_max_concurrent_sessions_per_token` (default 5) sessions per token; `POST /chat/sessions` returns 429 if the cap is hit. The UI surfaces only the active session in `localStorage`, so most users stay at one. The cap exists as a safety valve against runaway client bugs that create sessions without closing them.

### Settings additions

Append to `onto_platform/config.py`:

```python
chat_session_orphan_after_s: int = 1800        # 30 min
chat_turn_max_wall_clock_s: int = 1800         # 30 min, mirrors existing ingestion timeout
chat_sse_heartbeat_s: int = 15
chat_max_concurrent_sessions_per_token: int = 5  # safety valve
```

### What does NOT change in the backend

- All MCP tools (`mcp_tools_*.py`) — untouched.
- `run_agent`, `run_one_job` in `ingestion/workers.py` — untouched. The journaling decorator is added at the dispatcher boundary inside the chat-only callsite.
- Existing `/admin/ingestion/*` HTTP endpoints — kept (used by MCP-driven ingestion and as the upload backend for chat).
- Authentication / token store — untouched.

## Frontend

### Routing

Defined in `ui/src/main.tsx`. After redesign:

| Path | Component | Notes |
|---|---|---|
| `/login` | `LoginPage` | Kept; strings re-translated to zh-CN. |
| `/` | redirect | Server-side or client-side redirect to `/graph/staging`. |
| `/graph/:env` | `GraphPage` | `:env` ∈ `{staging, production}`. Tab toggle inside the page switches between them; the route param is the source of truth. |
| `/browse/:env` | `BrowserPage` | Same pattern as `/graph`. |
| `/chat` | `ChatPage` | NEW. Tries to resume from `localStorage.session_id`; if missing or 404, starts a new session. |

**Removed** (delete the components and their route entries):

- `/` Dashboard view
- `/diff` (DiffView)
- `/ingest` (IngestionPage — the old job-list)
- `/ingest/:job_id` (JobDetail)

Old `/diff` content (counts, "type PROMOTE to confirm") is preserved as a modal dialog opened from the toolbar buttons on `/graph/staging` and `/browse/staging`.

### Navigation (`AppLayout.tsx`, rewritten)

```
┌───────────────────────┐
│  Onto Platform        │
│  本体平台              │
├───────────────────────┤
│  图谱       Graph     │
│  浏览器     Browser   │
│  注入       Ingestion │
├───────────────────────┤
│  narcy188             │
│  退出登录             │
└───────────────────────┘
```

Three nav items, full Chinese labels, current-user identifier and sign-out at the bottom. Active item highlighted; selecting Graph or Browser preserves the current `:env` tab if any (default `staging`).

### Graph and Browser pages — staging/production tab toggle

The `:env` parameter drives a tab control rendered at the top of the page content:

```
┌────────────────────────────────────────────────────────────┐
│  图谱                                                       │
│  ┌─────────┬───────────┐                                   │
│  │ 暂存区  │  生产环境  │   [推送到生产 ▶] [回退暂存 ⟲]    │
│  └─────────┴───────────┘   (toolbar shown only on 暂存区)   │
│                                                              │
│  <ReactFlow graph or Browser table content>                 │
└────────────────────────────────────────────────────────────┘
```

Switching the tab navigates the route from `/graph/staging` ↔ `/graph/production` (so deep-linking works). The toolbar (`推送到生产` / `回退暂存`) is visible only on the staging tab.

### Promote / Revert toolbar behavior

- **推送到生产** opens a confirmation modal:
  - Counts: how many object_types / link_types / shared_property_types / interface_types / action_types will be added, modified, or removed.
  - A diff section showing the named entries (e.g., "+ object_type fact_orders", "- link_type order_status").
  - Existing safety gate: a text input requiring the user to type `PROMOTE` exactly. Submit button stays disabled until then.
  - On submit: calls existing MCP `promote_staging_to_production` via the `/mcp` endpoint (same path the e2e tests already exercise). Success toast, tab auto-switches to 生产环境.
- **回退暂存** opens a one-step "确认回退到当前生产环境的状态" dialog. On submit: calls existing `revert_staging_to_production`. Success toast, no tab switch.

Both toolbar buttons require admin scope (mirrors the existing tools' scopes). Editor-scope users see the staging tab and can chat, but the buttons are hidden. The current UI already does scope-gating via the `whoami` response on login; the new toolbar consults the same source.

### Chat page (`/chat`) — three-pane layout

```
┌──────────┬─────────────────────────┬─────────────────────────┐
│ Sidebar  │ Conversation             │ Live staging graph      │
│ nav      │                          │                         │
│          │ ┌────────────────────┐   │ ┌─────────────────────┐ │
│ 图谱     │ │ 对话 · sess_8f3a1c │   │ │ 暂存图谱 · 实时     │ │
│ 浏览器   │ │           保存 取消│   │ │   ● 同步中 · 1.5s   │ │
│ 注入 ●   │ ├────────────────────┤   │ ├─────────────────────┤ │
│          │ │ ── messages ──     │   │ │                     │ │
│          │ │  user message      │   │ │   <ReactFlow>       │ │
│          │ │  assistant message │   │ │                     │ │
│          │ │  ✓ tool_call       │   │ │                     │ │
│          │ │  ✓ tool_call       │   │ │                     │ │
│          │ │  ⏳ tool_call       │   │ │                     │ │
│          │ │                    │   │ │                     │ │
│          │ ├────────────────────┤   │ │                     │ │
│          │ │ [输入… 发送 ▶]     │   │ │                     │ │
│          │ │ 支持 .sql/.csv/.json   │ │                     │ │
│          │ └────────────────────┘   │ └─────────────────────┘ │
│ narcy188 │                          │                         │
│ 退出     │                          │                         │
└──────────┴─────────────────────────┴─────────────────────────┘
```

**Conversation pane (middle):**

- **Header:** session id + 保存 / 取消 buttons. Both buttons are disabled while a turn is in flight; a small "正在执行" indicator replaces them temporarily.
- **Messages list:**
  - User messages: right-aligned, blue bubble, with attached file chips below if any.
  - Assistant messages: left-aligned, dark-grey bubble, render markdown.
  - Tool calls: rendered *inline within the assistant's message* as monospace pills with a leading state icon — ✓ green (ok), ⏳ amber (in-flight), ✗ red (error). Click a pill to expand args/result JSON.
- **Input area:**
  - Single-line input expanding to multi-line, enter-to-send, shift-enter for newline.
  - **Drop zone is the entire conversation pane** (left half of the page). Visual drop overlay activates on dragenter. Files added show as chips under the input until sent.
  - File constraints surfaced inline ("支持 .sql/.csv/.json — 单文件上限 25 MB").
- **Auto-scroll** to bottom on new messages, except when the user has scrolled up (then show a "新消息 ↓" pill to jump back).

**Live staging graph pane (right):**

- Same `ReactFlow` component used on `/graph/staging` (extracted into a reusable `StagingGraphView` component).
- Header: title + a small status indicator. While `turn_in_flight === true` the indicator pulses amber and reads "● 处理中"; idle reads "○ 已同步".
- Fetches `get_registry(staging)` via React Query on mount, then refetches once per `turn_complete` SSE event. Does not poll on a fixed interval (staging only changes at turn boundaries because the existing agent commits one staging version per turn).
- **Decoupled from chat state.** The component receives `turn_in_flight: boolean` and an `onTurnComplete` invalidate-trigger (or shared queryKey to invalidate via `queryClient.invalidateQueries`) and is otherwise identical to the standalone `/graph/staging` view.

**Resume on reload:**

- On mount, read `session_id` from `localStorage`. If present, `GET /chat/sessions/{id}`. If 200, hydrate messages list. If 404, clear the storage entry and `POST /chat/sessions` to start fresh.
- If the resumed session has a turn in flight, immediately re-open SSE for it.

### i18n — hardcoded zh-CN

- All UI strings are written directly in JSX/TSX as Simplified Chinese.
- `<html lang="zh-CN">` and the existing `<meta charset="UTF-8">`.
- No `react-i18next`, no `lingui`, no locale JSON files.
- Backend error codes (`UNAUTHORIZED`, `FORBIDDEN`, `INVALID_OP`, `STAGING_LOCKED`, etc) are mapped to Chinese in a single `ui/src/api/errorMessages.ts` lookup. Unknown codes fall through to ``未知错误（${code}）``.
- Date / number formatting uses the browser's default locale (most installed browsers in zh-CN locale render `Intl.DateTimeFormat` correctly).

### Visual design — handoff to `frontend-design` skill

Locked in here:

- Dark theme, building on the existing `bg-zinc-950` baseline.
- Information-dense, technical-tool aesthetic. No marketing-style hero sections, gradients, or large illustrations.
- Subtle motion only — animations under 200 ms; no scroll-jacking or attention-grabbing transitions.

Delegated to `frontend-design`:

- Color palette refinements (accent colors, status colors for tool-call states ok/in-flight/error).
- Typography scale + zh-CN body font (e.g., Noto Sans SC, PingFang SC) and monospace for tool-call pills.
- Component spacing system, border radii, shadow language.
- Chat bubble polish; the wireframe shows colored rectangles, the skill produces the actual feel.
- "● 同步中" pulsing indicator visual treatment.
- File-drop hover overlay state.
- Tool-call card states (ok / in-flight / error) and the expanded args/result JSON view.
- Empty states for Graph / Browser when registries are empty.
- Promote modal layout — diff visualization (counts as numerical badges? as before/after silhouettes? this is the skill's call).

The implementation plan will include an explicit step that invokes `frontend-design:frontend-design` against the assembled chat page, the new nav shell, and the login page.

## Data Flow Walkthroughs

### 1. Open the chat page (cold start)

```
User → GET /chat (UI route)
UI:    read localStorage.session_id → null
UI:    POST /chat/sessions
backend: INSERT chat_sessions (id, token_id, status='active', created_at=now())
         RETURN { session_id }
UI:    localStorage.session_id = session_id
UI:    render empty conversation, render <StagingGraphView /> (one-shot fetch)
```

### 2. Drop a file and send a message

```
User drags logistics_facts.sql into the conversation pane.
UI:    POST /chat/sessions/{id}/uploads (multipart, single file)
backend: forwards to existing /admin/ingestion/uploads handler;
         INSERT ingestion_uploads (...);
         RETURN { upload_id }
UI:    chip rendered under input.

User types "把 fact_orders 加进去" + Enter.
UI:    POST /chat/sessions/{id}/turns { message, upload_ids: [<id>] }
backend: refuse if a turn is already running on this session (409);
         INSERT chat_messages (turn_index, role='user', content={text, upload_ids});
         INSERT ingestion_jobs row tagged with chat_session_id and turn_index;
         UPDATE chat_sessions SET last_turn_at = now();
         schedule run_one_job in background;
         RETURN { turn_id }
UI:    record turn_id; set turn_in_flight=true; open EventSource(GET /stream?turn_id=X).
```

### 3. SSE stream during the turn

```
backend (run_one_job under chat path):
  emit agent_step_start { step_index: 1 }
  LLM proposes tool_call put_object_type(definition={...}, ...)
  emit tool_call { sequence: 1, name: ..., args: ... }
  agent applies the call to its in-memory WorkingRegistry (no DB write yet)
  emit tool_result { sequence: 1, status: "ok", summary: "Buffered object_type rid=ri.obj.xxx into working registry" }
  ... repeat for each tool call (still all in-memory) ...
  LLM emits final assistant message
  emit assistant_message { content: "已分析 SQL 并将 fact_orders ...", partial: false }
  agent loop returns
  worker calls import_into_registry(snap.registry, wr.snapshot(), mode=...)
                 then rstore.save(env=staging, new_reg, expected_version=staging_version_at_start)
       — single atomic commit of the whole turn
  INSERT chat_messages (role='assistant', content={text})
  emit turn_complete { tool_calls_made: 5, new_staging_version: 47 }
  close stream

UI (SSE consumer):
  - tool_call → render amber pill with sequence=N
  - tool_result → flip pill green (or red on error)
  - assistant_message → render the assistant bubble
  - turn_complete → set turn_in_flight=false; trigger live graph refetch (queryClient.invalidateQueries(["full","staging"]))
  - turn_error → set turn_in_flight=false; render banner with the error message; do NOT refetch (staging didn't commit)

UI (live graph, parallel):
  - on mount: one-shot fetch get_registry(staging)
  - on each turn_complete: invalidate query, refetch once
  - no fixed-interval polling
```

### 4. Save (commit, end session)

```
User clicks 保存.
UI:    POST /chat/sessions/{id}/save
backend: refuse if a turn is in flight (409);
         UPDATE chat_sessions SET status='saving';
         DELETE FROM chat_sessions WHERE id = ... (ON DELETE CASCADE drops messages + journal)
         RETURN 204
UI:    localStorage.removeItem('session_id'); navigate('/graph/staging')
```

### 5. Cancel (restore pre-session snapshot, end session)

```
User clicks 取消.
UI:    POST /chat/sessions/{id}/cancel
backend: refuse if a turn is in flight (409);
         UPDATE chat_sessions SET status='cancelling';
         load chat_sessions row → pre_session_registry, pre_session_version
         current_staging_version = await rstore.load_version(s, Env.staging)
         try:
           await rstore.save(
             s, Env.staging, pre_session_registry,
             expected_version=current_staging_version,
             token_label="chat-cancel"
           )
         except StaleVersionError:
           # Another caller mutated staging concurrently; rollback would clobber.
           RETURN 409 { code: "STALE_STAGING", message: "..." }
           leave row in 'cancelling' for operator inspection
         on success:
           DELETE chat_sessions row (cascade drops chat_messages)
           RETURN 204
UI:    localStorage.removeItem('session_id'); navigate('/graph/staging')
       on 409: show modal "暂存区已被其他操作修改" with operator guidance.
```

### 6. Promote from /graph/staging

```
User on /graph/staging clicks 推送到生产.
UI:    fetch counts (see Open Question #1 for whether this is two existing
       /mcp list_* calls + client-side diff, or a new staging_vs_production_diff
       convenience tool)
UI:    render confirmation modal with counts + diff list
User types PROMOTE in the input → submit enabled
UI:    POST /mcp { method: "tools/call", params: { name: "promote_staging_to_production", args: {} } }
backend: existing tool runs (atomic rotate)
UI:    on success, toast 推送成功; switch tab to 生产环境.
```

## Testing Strategy

### Unit tests (`tests/unit/`)

- **Pre-session snapshot capture** — creating a session reads the current staging registry into `pre_session_registry`; verify the snapshot equals what `rstore.load(env=staging)` returned.
- **Cancel rollback** — given a session with a pre-session registry and current staging that's diverged (one turn applied), Cancel writes pre_session_registry as a new staging version and the row is deleted; staging matches pre-session state.
- **Cancel under StaleVersionError** — given staging changed unexpectedly between session start and Cancel (simulated by bumping staging version), the rollback raises `StaleVersionError`; endpoint returns 409 and leaves the row in `cancelling`.
- **Orphan recovery sweep** — a session marked `active` with `last_turn_at` 31 minutes ago is rolled back and deleted; staging matches pre-session state.

### Integration tests (`tests/integration/`)

- **Full session happy path** — start session, run one turn (StubLiteLLM scripts a put_object_type then a put_link_type), Save, verify staging contains the entities and the chat_sessions row is gone.
- **Cancel rolls back** — start session, run turn, Cancel, verify staging matches pre-session state and chat_sessions row is gone.
- **409 on concurrent turn** — start a turn, immediately POST another turn → 409.
- **409 on save during turn** — start a turn, immediately POST save → 409.
- **SSE event sequence** — drive a scripted turn, capture the event stream, assert the order is `agent_step_start, tool_call(seq=1), tool_result(seq=1), tool_call(seq=2), tool_result(seq=2), assistant_message, turn_complete`.
- **Resume after disconnect** — open SSE, mid-stream close the client, reopen with the same `turn_id` — receives the events emitted since reconnect (or all events if the journal/messages tables suffice as replay source). MAY: implement a minimal "replay buffered events" or document that reconnects only see future events. **Decision deferred to implementation plan.**

### End-to-end tests (`ui/tests/e2e/`)

Adopt the existing Playwright + axe-core setup. New specs:

- **chat_session.spec.ts** — drop a SQL fixture into the chat, send "把这个 SQL 文件里的所有表加进去", wait for `turn_complete`, verify ≥ 1 ✓ tool-call pill appears, verify the live graph shows ≥ 1 node, click Save, verify redirect to `/graph/staging`, verify the new node still visible there. (Real Volcengine LLM call.)
- **chat_cancel.spec.ts** — same setup but click 取消 instead. Verify the staging graph returns to its pre-session state. (Real Volcengine LLM call.)
- **promote_modal.spec.ts** — on `/graph/staging`, click 推送到生产, verify modal opens with diff counts, type `PROMOTE`, submit, verify success toast and tab switches to 生产环境.

Updated existing specs:

- **login.spec.ts** — replace English label/role queries with zh-CN equivalents (`getByRole("button", { name: /登录/ })`, `getByLabel("令牌")`).
- **ingestion.spec.ts** — replace with the new `chat_session.spec.ts` (covers the same backend pipeline through a different UI surface).
- The 3 data-dependent specs (`browse_graph`, `masking_display`, `diff_promote`) are kept skipped pending a seed-then-promote test fixture (left to a follow-up plan).

### Test infrastructure

- **StubLiteLLM scripts** for integration tests — pre-canned LLMResponse sequences that emit specific tool calls. Already exists in `onto_platform/ingestion/llm_client.py`.
- **Seed helper** for E2E tests that need data — a small Python helper invoked from a test setup that calls `import_full_registry_to_staging` with the existing logistics fixture, then `promote_staging_to_production`. Useful for the 3 currently-skipped data-dependent specs in a future round.

## Edge Cases & Error Handling

| Scenario | Behavior |
|---|---|
| Page reload mid-session (no turn running) | Hydrate from `GET /chat/sessions/{id}`. Messages list re-renders. No SSE opened. |
| Page reload mid-turn | Hydrate session; UI sees `status='active'` with the latest turn's events present in `chat_messages`. Re-open SSE for that turn_id; backend may already have emitted `turn_complete` — the GET returns the full state and SSE just yields nothing. |
| Two browser tabs same session | Both subscribe to the SSE fan-out queue; both receive the same events. Both have input disabled while a turn runs. Save / Cancel from either tab affects both (the other tab will get 404 on its next poll/SSE attempt and clear its localStorage). |
| LLM returns a malformed tool call | Backend logs, emits `tool_result{status: "error"}`, agent loop attempts to recover (existing `run_agent` handles this); UI renders the red ✗ pill. |
| LLM hits the 30-min wall clock | Backend emits `turn_error{kind: "timeout"}` and aborts. Tool calls already journaled stay journaled (Cancel still rolls them back). |
| Tool error mid-turn (e.g., delete refused due to inbound refs) | Backend emits `tool_result{status: "error", error: {code, message}}`; agent decides how to proceed (usually with a follow-up tool call or assistant message explaining the situation). |
| File upload exceeds 25 MB | Existing 422 response from `/admin/ingestion/uploads`; chat UI surfaces as a chat-pane error toast. |
| File upload of non-allowed extension | Same; surfaced as toast. |
| Concurrent Save + Turn | Save returns 409. UI re-enables save once turn completes. |
| Concurrent Cancel + Turn | Cancel returns 409. UI greys out cancel while turn runs and shows "正在执行" indicator. |
| Server crash during a turn | On restart, orphan recovery sweep finds the session (its `last_turn_at` is recent but `status='active'` with no live consumer); after 30 min idle, sweep replays the journal and drops the session. UI on next reload sees 404 and starts fresh. |
| Journal table grows large within a session | Bounded by per-job mutation count (existing `llm_max_steps`, default 50); soft cap. Single session journal is never huge. |
| Promote during active chat session | Allowed at the backend. The chat session's pre-session snapshot still reflects the registry at session start; Cancel may then raise `StaleVersionError` (because the staging version has moved), surfaced to the operator as 409. **Acknowledged risk** — operators are expected to coordinate; not worth a backend lock for this round. |
| Two concurrent chat sessions touching staging | The second session's first turn raises `StaleVersionError` at commit (existing optimistic concurrency in `rstore.save`), surfaced as a turn_error. The session can recover by reloading staging and retrying the turn. Cancel of the first-completing session works normally; Cancel of the later session may also raise StaleVersionError. **Acknowledged risk** — lockless for this round. |

## Open Questions / Followups for the Implementation Plan

1. **Diff counts endpoint** — does the existing MCP tool surface support a single call that returns counts for the promote modal, or do we need to add a `staging_vs_production_diff` convenience tool? Decide during implementation. If we add a tool, it goes in `mcp_tools_read.py` (read-scope, no mutation).
2. **SSE event replay on reconnect** — if a client reconnects mid-turn, do we re-emit events the client already saw, only future ones, or compute a "since last sequence" param? Implementation plan should pick one. Default proposal: the GET `/chat/sessions/{id}` returns all messages so far; SSE only emits future events. The client reconciles by reading the GET first.
3. **Concurrent-session lock** — the v1 is lockless (acknowledged risk above). Do we want a per-token soft lock that warns the user "你已有一个会话在 X 分钟前打开，要恢复吗？"? Probably yes for UX; cheap to add. Implementation plan should include it as a secondary item.
4. **Skipped E2E specs** — the 3 data-dependent specs (`browse_graph`, `masking_display`, `diff_promote-admin`) need a seed step. The implementation plan should call out whether to enable them now (with a seed fixture) or keep them skipped.
5. **Visual design fidelity** — `frontend-design` is invoked once during implementation, on the chat page + nav shell + login page. Do we need a second pass for Graph and Browser? Likely yes, but the plan can split it into two iterations to keep blast radius small.

## File Manifest (Implementation Targets)

### New files

```
onto_platform/chat/__init__.py
onto_platform/chat/http.py            -- HTTP endpoints (FastAPI router)
onto_platform/chat/orchestrator.py    -- ChatSession lifecycle, pre-session snapshot capture, cancel rollback
onto_platform/chat/sse.py             -- SSE fan-out queue + heartbeat helper
onto_platform/chat/recovery.py        -- orphan-session sweep
migrations/versions/<timestamp>_chat_sessions.py
ui/src/views/chat/ChatPage.tsx
ui/src/views/chat/ConversationPane.tsx
ui/src/views/chat/MessageBubble.tsx
ui/src/views/chat/ToolCallPill.tsx
ui/src/views/chat/StagingGraphPane.tsx
ui/src/api/chat.ts                    -- typed client for /chat/* endpoints + SSE
ui/src/api/errorMessages.ts           -- backend code → zh-CN string
ui/src/components/PromoteModal.tsx
ui/src/components/RevertModal.tsx
tests/unit/test_chat_orchestrator.py    -- snapshot capture, cancel rollback, StaleVersionError handling
tests/unit/test_chat_recovery.py        -- orphan sweep
tests/integration/test_chat_session.py
tests/integration/test_chat_sse_stream.py
ui/tests/e2e/chat_session.spec.ts
ui/tests/e2e/chat_cancel.spec.ts
ui/tests/e2e/promote_modal.spec.ts
```

### Modified files

```
onto_platform/app.py                  -- mount /chat router; wire orphan recovery into lifespan
onto_platform/config.py               -- add chat_* settings
onto_platform/bootstrap.py            -- call orphan recovery on startup
ui/src/main.tsx                       -- routing changes (drop /, /diff, /ingest, /ingest/:job_id; add /chat)
ui/src/components/AppLayout.tsx       -- 3 nav items, Chinese strings
ui/src/views/login/Login.tsx          -- Chinese strings
ui/src/views/browse/OntologyBrowser.tsx  -- tab toggle staging/production + toolbar on staging
ui/src/views/graph/GraphView.tsx      -- tab toggle + toolbar on staging
ui/src/index.html                     -- lang=zh-CN
ui/tests/e2e/login.spec.ts            -- zh-CN labels
.gitignore                            -- add .superpowers/, ui/test-results/, ui/node_modules/ if missing
```

### Deleted files (after redesign)

```
ui/src/views/Dashboard.tsx
ui/src/views/diff/DiffView.tsx
ui/src/views/ingestion/IngestionPage.tsx
ui/src/views/ingestion/JobDetail.tsx
ui/tests/e2e/ingestion.spec.ts        -- replaced by chat_session.spec.ts
ui/tests/e2e/diff_promote.spec.ts     -- replaced by promote_modal.spec.ts (admin variant only)
```

## References

- Existing backbone design: `docs/superpowers/specs/2026-04-25-ontology-platform-backbone-design.md`
- Existing ingestion plan: `docs/superpowers/plans/2026-04-25-02-ingestion.md`
- MCP tools (read): `onto_platform/mcp_tools_read.py`
- MCP tools (editor — the journaling targets): `onto_platform/mcp_tools_editor.py`
- MCP tools (admin — promote/revert): `onto_platform/mcp_tools_admin.py`
- Agent loop: `onto_platform/ingestion/workers.py` (functions `run_one_job`, `run_agent`)
- Auth dependency: `onto_platform/ui_auth.py` (`require_scope_via_cookie_or_bearer`)
- Wireframe (committed alongside this spec): `docs/superpowers/specs/2026-04-28-onto-platform-ui-redesign-wireframe.html`

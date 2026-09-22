# SangamMW — Implementation Plan

**Date:** 2026-09-21  
**Updated:** 2026-09-22  
**Status:** ✅ ALL PHASES COMPLETE (0–14)  
**Repo:** `sangam-mw/` (single repo, `backend/` + `frontend/`)

---

## Phase Status

| Phase | Name | Status | Completed |
|---|---|---|---|
| 0 | Foundation | ✅ DONE | 2026-09-21 |
| 1 | Connector Framework | ✅ DONE | 2026-09-21 |
| 2 | Reference Connectors | ✅ DONE | 2026-09-21 |
| 3 | Transform Engine | ✅ DONE | 2026-09-21 |
| 4 | Flow Engine & Orchestration | ✅ DONE | 2026-09-21 |
| 5 | Visual Canvas & Designer UI | ✅ DONE | 2026-09-22 |
| 6 | Connector Ecosystem | ✅ DONE | 2026-09-22 |
| 7 | Enterprise & Production | ✅ DONE | 2026-09-22 |
| 8 | API Management & Gateway | ✅ DONE | 2026-09-22 |
| 9 | Production Hardening | ✅ DONE | 2026-09-22 |
| 10 | Test Suite | ✅ DONE | 2026-09-22 |
| 11 | Frontend Completion | ✅ DONE | 2026-09-22 |
| 12 | Notifications, Lineage & Templates | ✅ DONE | 2026-09-22 |
| 13 | Scheduler UI, Health & AI Debug | ✅ DONE | 2026-09-22 |
| 14 | App Insights & Observability Platform | ✅ DONE | 2026-09-22 |

---

## Phase 14 — App Insights & Observability Platform

> Inspired by MuleSoft Anypoint Insights and EAIESB Boomi/Mule App Insights. Zero user action required — the flow engine auto-instruments every run. Developers get message-level tracing, cross-flow dashboards, log search, trend analytics, and business event tracking out of the box.

### Design Principle

Instrument **once** in `FlowExecutor`. Every run automatically produces:
- A persisted `ExecutionRun` + `StepExecution` in Postgres (replacing the current in-memory `_runs` dict)
- A `correlation_id` threaded through every event, log line, and record header
- Rolled-up metrics in `MetricsBucketTable` (pre-aggregated — fast dashboard queries with no GROUP BY scans)
- An append-only `ExecutionLogTable` (full-text indexed — powers log search)
- Optional `BusinessEventTable` entries when flows call `execution_context.emit("event.name", {...})`

---

### Phase 14 — Step-by-step implementation plan

#### Step 1 — DB Layer (Alembic migrations)

**New tables:**

| Table | Key columns | Purpose |
|---|---|---|
| `ExecutionRunTable` | `run_id` (PK), `flow_id`, `flow_name`, `status`, `correlation_id`, `trigger_type`, `triggered_by`, `started_at`, `ended_at`, `duration_ms`, `rows_processed`, `rows_failed`, `error_message` | Persists every run — replaces `_runs` dict |
| `StepExecutionTable` | `id`, `run_id` (FK), `step_id`, `step_type`, `connector_id`, `status`, `duration_ms`, `rows_in`, `rows_out`, `rows_failed`, `error_type`, `error_message`, `started_at`, `ended_at` | Per-step timing and row counts |
| `ExecutionLogTable` | `id`, `run_id`, `flow_id`, `step_id`, `correlation_id`, `level` (DEBUG/INFO/WARN/ERROR), `message`, `payload_preview` (512 chars of JSON), `timestamp` | Append-only log, full-text indexed on `message` and `flow_id` |
| `MetricsBucketTable` | `flow_id`, `bucket_ts` (truncated to minute), `run_count`, `error_count`, `total_rows`, `total_duration_ms`, `p50_ms`, `p95_ms`, `p99_ms` | Pre-aggregated time-series for dashboard trend charts; upserted on every run completion |
| `BusinessEventTable` | `id`, `flow_id`, `run_id`, `step_id`, `correlation_id`, `event_name`, `payload` (JSONB), `occurred_at` | Custom domain events emitted by user flows via SDK call |

**Files:**
- `backend/sangam_mw/db/tables.py` — append 5 new table classes
- `backend/alembic/versions/<rev>_add_observability_tables.py` — migration

---

#### Step 2 — Engine Instrumentation

**File:** `backend/sangam_mw/engine/executor.py`

Changes:
- Generate `correlation_id = str(uuid4())` at the top of `execute()`
- Thread `correlation_id` into `ExecutionRun`, every `StepExecution`, and every `FlowEvent`
- After `execute()` returns (success or failure): call `await _persist_run(run, session)` — writes `ExecutionRunTable` + all `StepExecutionTable` rows
- Add `_log_event(run_id, step_id, level, message, payload_preview)` helper — appends to `ExecutionLogTable`
- Call `_log_event()` at: step start, step complete, step error, run complete, run fail
- After persistence: call `await _upsert_metrics_bucket(flow_id, duration_ms, status, rows)` — upserts `MetricsBucketTable`

**File:** `backend/sangam_mw/engine/execution_context.py` (new or extend existing)

Add `emit(event_name: str, payload: dict)` method on `ExecutionContext` — inserts into `BusinessEventTable` with the run's `correlation_id`.

---

#### Step 3 — Insights API Routes

**File:** `backend/sangam_mw/api/routes/insights.py` (new)

| Endpoint | Description |
|---|---|
| `GET /insights/overview` | Summary tiles: total_flows, runs_today, error_rate_today, avg_duration_ms, runs_by_status counts |
| `GET /insights/flows` | Per-flow table: flow_id, flow_name, run_count, error_count, error_rate, avg_duration_ms, last_run_at, last_status. Sortable, filterable by status/date. |
| `GET /insights/flows/{flow_id}/runs` | Paginated run history for one flow. Filters: status, from_dt, to_dt, triggered_by. Returns runs with step summary. |
| `GET /insights/flows/{flow_id}/metrics` | Time-series data from `MetricsBucketTable`. Params: granularity (minute/hour/day), from_dt, to_dt. Returns array of `{ts, run_count, error_count, p50_ms, p95_ms, p99_ms}` |
| `GET /insights/logs` | Full-text log search across `ExecutionLogTable`. Params: q (search string), flow_id, run_id, level, from_dt, to_dt, limit, offset. |
| `GET /insights/logs/{run_id}` | All log lines for a single run, ordered by timestamp. |
| `GET /insights/events` | Business events. Params: flow_id, event_name, correlation_id, from_dt, to_dt. |
| `GET /insights/runs/{run_id}` | Full run detail: ExecutionRun + all StepExecution rows + log lines + business events. Single-page view for the execution browser. |

All routes: require `FLOW_READ` permission. Registered in `main.py` at `/api/v1`.

---

#### Step 4 — External Log Forwarder (pluggable)

**File:** `backend/sangam_mw/observability/forwarder.py` (new)

```
LogForwarder (ABC)
├── ELKForwarder       — POST to Elasticsearch /_bulk
├── AzureForwarder     — POST to Azure Application Insights ingestion endpoint  
├── LokiForwarder      — POST to Grafana Loki /loki/api/v1/push
└── DatadogForwarder   — POST to Datadog /api/v2/logs
```

- Config via env vars: `LOG_FORWARDER=elk`, `LOG_FORWARDER_URL=https://...`, `LOG_FORWARDER_API_KEY=...`
- Async, fire-and-forget — forwarder failures never block a flow run
- Batched: buffers 100 events or 5 seconds, whichever comes first, then flushes
- Called from `_log_event()` after DB write

---

#### Step 5 — Frontend: Insights Dashboard

**File:** `frontend/src/pages/InsightsPage.tsx` + `InsightsPage.css`

Sections:
1. **Summary bar** — 4 tiles: Flows monitored, Runs today, Error rate (%), Avg latency. Each with delta vs yesterday.
2. **Flow health table** — columns: Flow name, Runs (24h), Errors, Error rate, Avg duration, Last run (relative time), Status badge. Click row → `/insights/flows/:id`.
3. **Global trend chart** — line chart: runs/min + error rate over last 24h. Time-range selector: 1h / 6h / 24h / 7d.

**File:** `frontend/src/pages/FlowInsightsPage.tsx`

Per-flow detail page at `/insights/flows/:id`:
1. **Stat tiles** — runs, errors, p50/p95/p99 latency, total rows processed
2. **Trend charts** — throughput line + error rate line + latency percentile lines, same time-range selector
3. **Run history table** — paginated list of executions with status badge, duration, rows, triggered_by, timestamp. Click → opens run detail drawer.
4. **Run detail drawer** — step waterfall (already built in RunsPage) + log timeline (new: log lines from `ExecutionLogTable`) + business events (if any)

---

#### Step 6 — Frontend: Log Search

**File:** `frontend/src/pages/LogSearchPage.tsx` + `LogSearchPage.css`

Layout:
- **Search bar** — full-text input with real-time debounce (300ms). `q=` sent to `GET /insights/logs`.
- **Filter strip** — Flow selector, Level (ALL / INFO / WARN / ERROR), Date range picker (from/to), Run ID input.
- **Results list** — each row: `[timestamp] [level badge] [flow_id] [step_id] message`. Matched query terms highlighted in yellow. Click → navigate to `/insights/flows/:id?run=:run_id`.
- **Pagination** — load-more button, shows `X of Y results`.
- **Empty / error states** — "No logs matching…", "Enter a search term to begin".

---

#### Step 7 — Frontend: Execution Browser Enhancement

**File:** `frontend/src/pages/RunsPage.tsx` (update)

Changes to existing page:
- Fetch runs from `GET /insights/runs` (DB-backed) instead of in-memory `GET /runs/`
- Add filter bar: Flow selector, Status, Date range, Triggered by
- In `RunDetail` panel: below the step waterfall, add **Log Timeline** — log lines from `GET /insights/logs/{run_id}`, colour-coded by level (INFO=grey, WARN=amber, ERROR=red)
- Add **Business Events** sub-panel below log timeline (only if events exist)
- Add **Correlation ID** chip in the run header — click copies to clipboard, navigates to log search pre-filtered by that correlation_id

---

#### Step 8 — Frontend: Business Events View

**File:** `frontend/src/pages/BusinessEventsPage.tsx` + `BusinessEventsPage.css`

- Table: Event name, Flow, Run ID, Correlation ID, Timestamp, Payload preview (expandable JSON)
- Filters: event_name selector, flow_id selector, date range, correlation_id input
- Used by ops teams to track domain-level outcomes (e.g., "how many `order.created` events fired today?")

---

#### Step 9 — Route & Nav Wiring

**`frontend/src/App.tsx`** — add routes:
- `/insights` → `<InsightsPage>` (viewer+)
- `/insights/flows/:id` → `<FlowInsightsPage>` (viewer+)
- `/logs` → `<LogSearchPage>` (viewer+)
- `/events` → `<BusinessEventsPage>` (viewer+)

**`frontend/src/components/ui/AppHeader.tsx`** — add nav links:
- **Insights** (→ `/insights`)
- **Logs** (→ `/logs`)

---

#### Step 10 — API Client & Types

**`frontend/src/api/insights.ts`** (new)

Types: `InsightsOverview`, `FlowInsight`, `RunHistory`, `MetricsBucket`, `LogEntry`, `BusinessEvent`, `RunDetail`

Functions: `insightsApi.overview()`, `.flows()`, `.flowRuns(flowId, params)`, `.flowMetrics(flowId, params)`, `.searchLogs(params)`, `.runLogs(runId)`, `.businessEvents(params)`, `.runDetail(runId)`

---

#### Step 11 — Unit Tests

**`backend/tests/unit/test_insights.py`** (new)

- `TestMetricsBucket`: upsert creates new bucket, upsert increments existing, error_count correct on failed run, p95 calculation
- `TestExecutionLogTable`: append log, level filter, full-text match, payload_preview truncation at 512 chars
- `TestBusinessEvent`: emit stores correct fields, correlation_id propagated, payload JSONB round-trip
- `TestInsightsApi`: overview counts, flow list sorting, log search q param, run detail includes steps + logs

---

#### Phase 14 — Summary of new files

| File | Type |
|---|---|
| `db/tables.py` | +5 table classes |
| `alembic/versions/*_observability.py` | DB migration |
| `engine/executor.py` | instrument: persist + log + metrics |
| `engine/execution_context.py` | `emit()` for business events |
| `observability/forwarder.py` | pluggable log forwarder (ELK/Azure/Loki/Datadog) |
| `api/routes/insights.py` | 8 new API endpoints |
| `api/main.py` | register insights router |
| `tests/unit/test_insights.py` | unit tests |
| `frontend/src/api/insights.ts` | typed API client |
| `frontend/src/pages/InsightsPage.tsx` + `.css` | cross-flow dashboard |
| `frontend/src/pages/FlowInsightsPage.tsx` + `.css` | per-flow analytics + run detail |
| `frontend/src/pages/LogSearchPage.tsx` + `.css` | full-text log search |
| `frontend/src/pages/BusinessEventsPage.tsx` + `.css` | business event timeline |
| `frontend/src/pages/RunsPage.tsx` | update: DB-backed, log timeline, correlation chip |
| `frontend/src/App.tsx` | +4 routes |
| `frontend/src/components/ui/AppHeader.tsx` | +2 nav links |

### Phase 13 deliverables (completed 2026-09-22)
- **23/23 unit tests passing** — scheduler helper/validation tests
- **Backend: Flow Scheduler** (`api/routes/scheduler.py`)
  - `JobCreate` pydantic model with mutual-exclusion validator (cron XOR interval)
  - `ScheduledFlowTable` in `db/tables.py` — `flow_id` (unique), `cron_expr`, `interval_seconds`, `timezone`, `is_active`, `last_run_at`
  - Routes: `GET/POST /scheduler/jobs`, `GET/PATCH/DELETE /scheduler/jobs/{flow_id}`, `POST /scheduler/jobs/{flow_id}/trigger`
  - Upsert semantics on `POST /jobs` (updates existing row if flow_id already present)
  - `_cron_human()` converts common patterns to readable labels; croniter optional (`_HAS_CRONITER` flag)
  - Registered in `main.py` at `/api/v1/scheduler`
- **Backend: AI Debug** (`api/routes/executions.py`)
  - `POST /runs/{run_id}/debug` — builds failure context, tries Anthropic AI, falls back to `_rule_based_suggestion()` matching timeout/auth/connection/null patterns
- **Backend: Connection Health** (`api/routes/connectors.py`)
  - `GET /connectors/health` — bulk status check for all registered connectors; returns `{total, available, connectors, checked_at}`
- **Frontend: SchedulerPage** (`SchedulerPage.tsx` + `SchedulerPage.css`)
  - Scheduled jobs table: cron/interval badge, trigger label, next/last run timestamps, active status
  - Create form: flow selector, cron preset dropdown + custom input, interval mode with human-readable hint, timezone, start-active toggle
  - Inline enable/disable toggle, "Run now" button, delete button per job
- **Frontend: AI Debug panel** in `RunsPage.tsx`
  - `AiDebugPanel` component — "Debug with AI" button appears only on failed/timed-out runs
  - Shows AI-powered or rule-based suggestion inline; labels which mode was used; hides AI-error detail in small note
- **Frontend: Connection health** in `ConnectionsPage.tsx`
  - `HealthBadge` per card — green "healthy" or red "unavailable/error"; auto-refreshes every 30 s
  - "Test all" button triggers bulk `/connectors/health` refetch; health summary chip shows `N/M healthy`
  - `ConnectorHealthReport`/`ConnectorHealthEntry` types added to `api/connectors.ts`
- `frontend/src/api/scheduler.ts` — `ScheduledJob`, `CreateJob` types; `schedulerApi` client
- `AppHeader` updated with Scheduler nav link
- `App.tsx` updated with `/scheduler` (operator+) route
- **Zero TypeScript errors** — full `tsc --noEmit` pass

### Phase 12 deliverables (completed 2026-09-22)
- **296/296 unit tests passing** — 24 new tests for notification engine
- **Backend: Notification Engine** (`sangam_mw/notifications/`)
  - `channels.py` — `SlackChannel` (Incoming Webhook), `WebhookChannel` (HMAC-SHA256 signed); `channel_from_dict` factory
  - `rules.py` — `AlertTrigger` enum (5 triggers), `AlertRule` dataclass with `matches()` supporting flow-id filter, threshold conditions
  - `dispatcher.py` — `NotificationDispatcher`: `dispatch(event_type, context)`, `add_rule`/`remove_rule`/`load_rules`; `get_dispatcher()` global singleton
  - `db.tables.AlertRuleTable` — persisted alert rules with JSONB channels/conditions/flow_ids
  - `api/routes/notifications.py` — CRUD routes + `POST /rules/{id}/test` for live channel test
  - Registered in `main.py` at `/api/v1/notifications`
- **Frontend: Lineage page** (`LineagePage.tsx`) — flow selector shows sources/sinks as edge cards with connector + object + step info; impact analysis form (connection_id/connector_id/object_name → affected flows list)
- **Frontend: Templates page** (`TemplatesPage.tsx`) — browse all templates with category filter + search; template card grid; instantiate modal with parameter + connection-mapping form → creates flow and navigates to designer
- **Frontend: Notifications page** (`NotificationsPage.tsx`) — list/create/toggle/delete alert rules; create form with trigger selector, threshold conditions, Slack or webhook channel config; test button fires live notification
- `frontend/src/api/lineage.ts` + `notifications.ts` — typed API clients for new endpoints
- `AppHeader` updated with Templates, Lineage, Alerts nav links
- `App.tsx` updated with `/lineage`, `/templates` (developer+) and `/notifications` (operator+) routes

### Phase 11 deliverables (completed 2026-09-22)
- **Zero TypeScript errors** — full `tsc --noEmit` pass across all new files
- `frontend/src/api/auth.ts` — Login, me, logout, Google OAuth, SAML metadata; `loginAndStore` helper
- `frontend/src/api/gateway.ts` — Full gateway management API (products, keys, analytics, webhooks)
- `frontend/src/api/admin.ts` — Admin API (users, audit log, system stats)
- `frontend/src/store/authStore.ts` — Zustand persist store: `UserRole`, `ROLE_RANK`, `setAuth`, `logout`, `isAuthenticated`, `hasRole`
- `frontend/src/components/ui/ProtectedRoute.tsx` — Route guard redirecting to `/login` or showing access-denied
- `frontend/src/pages/LoginPage.tsx` — Login form (email/password, Google OAuth button, SAML link)
- `frontend/src/pages/DashboardPage.tsx` — Stats tiles, flows table, quick-actions panel, user/role display
- `frontend/src/pages/GatewayPage.tsx` — API products list, YAML create form, product detail with keys and analytics tiles, webhook list
- `frontend/src/pages/AdminPage.tsx` — Tabbed admin portal: Users (role edit, deactivate), Audit Log (hash-chain verify), System (stats)
- `frontend/src/components/ui/RunMonitor.tsx` — SSE-based live execution event feed
- `frontend/src/components/ui/AppHeader.tsx` — Updated: user avatar, role badge, logout button, gateway/admin nav links
- `frontend/src/App.tsx` — Updated routing: `/login` public, all other routes in `ProtectedRoute`; `/gateway` requires developer+; `/admin` requires admin

### Phase 10 deliverables (completed 2026-09-22)
- **272/272 unit tests passing** — 0 failures across all 10 phases
- 10 new unit test files covering Phases 7–9 (`tests/unit/`):
  - `test_rbac.py` — 4-tier role hierarchy, permission enforcement, unknown-role denial
  - `test_audit_log.py` — `_compute_hash` determinism, chain integrity, `AuditAction` enum
  - `test_rate_limiter.py` — sliding window counter, per-minute/day limits, headers, reset
  - `test_api_keys.py` — `smw_` prefix, SHA-256 hash, create/validate/revoke/list lifecycle
  - `test_vault.py` — Fernet encrypt/decrypt round-trip, Unicode, missing-key error
  - `test_env_config.py` — `${VAR}` interpolation, `resolve_connection`, `feature_enabled`, `promote`
  - `test_webhooks.py` — subscribe/unsubscribe, HMAC-SHA256 signing, async dispatch routing
  - `test_oas_spec.py` — `OasParser.parse`, `OasExporter.to_yaml`, `FlowToOas.extract_path`
  - `test_gateway_proxy.py` — `_apply_transform` all modes, `GatewayProxy` product registry
  - `test_flow_testing.py` — `FlowTestSuite.from_yaml`, `OutputAssertion.check`, runner report
- 4 integration test files (`tests/integration/`):
  - `test_api_health.py` — `/health`, `/health/ready`, `/metrics` via TestClient
  - `test_api_scim.py` — full SCIM 2.0 CRUD, 409 duplicate, 404 not-found, 401 missing token
  - `test_api_gateway.py` — product CRUD, key management, analytics endpoints
  - `test_api_portal.py` — public portal listing, 404 for unknown products
- `pyproject.toml` dev group updated: added `anyio[trio]>=4.0.0`
- Fixed pre-existing `test_api_routes.py::test_health` assertion against updated health schema

### Phase 9 deliverables (completed 2026-09-22)
- GitHub Actions CI: lint (ruff), typecheck (mypy), unit tests, integration tests with Postgres service, Docker build smoke test (`.github/workflows/ci.yml`)
- Makefile: `make dev/test/lint/fmt/typecheck/migrate/docker-up/deploy/key/clean` — full devex automation
- `docker-compose.prod.yml`: nginx + backend + postgres + prometheus + grafana, health checks, rolling deploy
- Multi-stage `Dockerfile`: builder → production, non-root user, read-only filesystem, HEALTHCHECK
- Kubernetes manifests (`k8s/deployment.yaml`): Deployment, Service, Ingress, HPA (CPU+memory), PodDisruptionBudget, initContainer migration
- HashiCorp Vault secrets backend (`vault/provider.py`): Vault transit encrypt/decrypt + KV v2 read/write; Fernet remains default; switch via `SECRETS_BACKEND=vault`
- Multi-environment config (`env/config.py`): `sangam-envs.yaml` with connection aliases per env; `${ENV_VAR}` interpolation; `MultiEnvConfig.promote()` for alias-safe promotion
- SCIM 2.0 user provisioning (`routes/scim.py`): RFC 7643/7644 — list/create/get/put/patch/delete; Okta / Azure AD compatible
- Enhanced health check (`routes/health.py`): `GET /health/ready` (DB + connectors + secrets), `GET /health/deps` (admin Vault/Prometheus detail)
- `sangam deploy` CLI: git-native deploy to named environment, dry-run mode, glob flow files
- `sangam env list/resolve` CLI: list environments and resolve connection aliases
- Prometheus alerting rules (`monitoring/prometheus-rules.yml`): error rate, P99 duration, row anomaly, no-runs, slow connector
- Grafana dashboard JSON (`monitoring/grafana-dashboard.json`): runs/min, error rate, P50/P95/P99 latency, rows processed, connector op latency

### Phase 8 deliverables (completed 2026-09-22)
- API Gateway proxy: `GET/POST/PUT/PATCH/DELETE /api/v1/gw/{product_id}/{path}` routes all inbound to flows
- API Products & Plans: YAML-defined products with endpoints, rate-limit plans, auth config (`gateway/api_product.py`)
- Rate limiting: sliding window per-consumer (per-minute + per-day), in-memory, Redis-ready (`gateway/rate_limiter.py`)
- API key management: SHA-256 hashed keys, `smw_` prefix, scoped per product/plan, revocable (`gateway/api_keys.py`)
- Analytics: p50/p95/p99 latency, error rate, req/sec, top consumers — per endpoint and per product (`gateway/analytics.py`)
- Developer portal: public `GET /portal/products`, self-register `POST /portal/products/{id}/register`, spec download, usage dashboard
- OAS 3.0: parse spec → ApiProductDef, export ApiProductDef → OAS YAML, generate flow skeleton per operationId (`oas/spec.py`)
- Request/response transform: declarative rename_fields / include_fields / exclude_fields / wrap_key in endpoint config
- Mock API endpoints: set `mock_response` in endpoint → gateway returns canned JSON without invoking any flow
- Webhook outbound: subscribe/unsubscribe, HMAC-SHA256 signed delivery, exponential backoff retry, dead-letter, redeliver API
- DB tables: ApiProductTable, ApiKeyTable, ApiUsageTable, WebhookSubscriptionTable, WebhookDeliveryTable (6 new tables)

### Phase 7 deliverables (completed 2026-09-22)
- RBAC: 4-tier role hierarchy (admin > developer > operator > viewer), 18 permissions, `require_permission()` FastAPI dependency factory
- Hash-chained audit log: SHA-256 chain, SOC 2 / HIPAA / ISO 27001 compliant; export NDJSON, verify chain integrity
- Data lineage: `FlowLineageTable` records read/write per step; `impact_analysis()` for upstream/downstream impact
- SAML 2.0 SSO: SP-initiated flow via python3-saml; attribute mapping; JWT issuance; `/auth/saml/metadata` XML
- Flow testing framework: `sangam test <suite.yaml>` runs mock-based tests with no live connections; CI-ready
- AI flow generation: `POST /ai/generate-flow` and `POST /ai/suggest-mapping` via Anthropic/OpenAI
- Prometheus metrics: `GET /metrics` endpoint; Counter/Histogram/Gauge for runs, rows, connector ops
- Users API: `GET/PATCH /users` with self-demotion guard
- `sangam test` CLI command for running test suites locally

### Phase 6 deliverables (completed 2026-09-22)
- 9 new connectors: Kafka, Redis, MongoDB, BigQuery, Snowflake, Slack, OpenAI, Anthropic, HTTP Sidecar
- 14 total connectors registered in `pyproject.toml` entry-points
- Community connector SDK: `sangam connector new <name>` scaffolds full package
- Integration template marketplace: 5 YAML templates + `GET/POST /api/v1/templates` API
- Optional dependency groups per connector family in `pyproject.toml`

---

## 1. Vision

SangamMW is an **open-source middleware / iPaaS platform** competitive with Boomi, MuleSoft, SAP CPI, and Workato. It sits at the integration and API layer for data engineers, platform engineers, and AI teams who want:

- SQL and Python transforms (not DataWeave, not Groovy — skills they already have)
- A visual canvas like Boomi/MuleSoft but with YAML as the source of truth in git
- A connector framework where building a new connector is 6 methods, not a Java SDK
- Open source, self-hostable, `pip install` extensibility

**Positioning:** Python-native, git-native, AI-native. The middleware for the data engineering generation.

---

## 2. Tech Stack (all decisions final)

| Layer | Technology | Why |
|---|---|---|
| Core engine | Python 3.11+ / FastAPI | Data ecosystem, AI/ML, DuckDB, PySpark, existing codebase |
| Web framework | FastAPI + uvicorn | Async, Pydantic v2, OpenAPI auto-gen |
| Transform (small) | pandas + DuckDB | In-process, zero setup, SQL on DataFrames |
| Transform (large) | PySpark (subprocess) | Auto-promoted at 500K+ rows |
| Type safety | Pydantic v2 + mypy | Models for all config/runtime objects |
| Metadata database | **PostgreSQL only** | Single engine for local dev + production |
| ORM + migrations | SQLAlchemy 2 + Alembic | Async-compatible, migration-first |
| Secrets | Fernet (cryptography) | Symmetric encryption for all connector credentials |
| Scheduler | APScheduler 4 | Cron + interval triggers, persisted to Postgres |
| Platform auth | **JWT + Google OAuth2** | python-jose + authlib, no password management |
| Visual canvas | React Flow (MIT) | Same as n8n, Langflow — drag/drop node canvas |
| Inline code editor | Monaco Editor | VS Code's editor in browser, SQL + Python |
| Frontend | React + TypeScript + Vite | AgentStudio toolchain, same team |
| CLI | Python + Typer | `sangam deploy`, `sangam test`, `sangam connector` |
| Container | Docker Compose | FastAPI + Postgres + LocalStack (S3 mock) |
| CI | GitHub Actions | ruff + mypy + pytest on every PR |
| Secrets (enterprise) | HashiCorp Vault (Phase 7) | Alternative to Fernet for enterprise deployments |

---

## 3. Repo Structure

```
sangam-mw/
├── backend/
│   ├── pyproject.toml              # hatch, Python 3.11+, dependencies
│   ├── sangam_mw/
│   │   ├── connectors/
│   │   │   ├── base/               # BaseConnector, SourceMixin, SinkMixin, metadata
│   │   │   ├── file/               # FileConnector — reference implementation
│   │   │   ├── salesforce/         # SalesforceConnector — OAuth2 reference
│   │   │   ├── aws_s3/
│   │   │   ├── postgres/
│   │   │   └── rest_api/
│   │   ├── transforms/
│   │   │   ├── engine_router.py    # pandas < 500K, PySpark >= 500K
│   │   │   ├── duckdb_engine.py
│   │   │   ├── pandas_engine.py
│   │   │   ├── spark_engine.py
│   │   │   └── sandbox.py          # RestrictedPython
│   │   ├── engine/
│   │   │   ├── dag_parser.py       # Kahn topological sort, cycle detection
│   │   │   ├── executor.py         # FlowExecutor, ExecutionContext
│   │   │   ├── validator.py        # deploy-time pre-flight checks
│   │   │   └── scheduler.py        # APScheduler integration
│   │   ├── api/
│   │   │   ├── main.py             # FastAPI app
│   │   │   ├── routes/
│   │   │   │   ├── flows.py        # CRUD flow definitions
│   │   │   │   ├── execute.py      # POST /execute, GET /runs
│   │   │   │   ├── connectors.py   # test, preview, introspect
│   │   │   │   └── gateway.py      # Phase 8: API gateway routes
│   │   │   └── auth.py             # JWT + Google OAuth2
│   │   ├── models/
│   │   │   ├── flow.py             # FlowDefinition, StepConfig
│   │   │   ├── execution.py        # ExecutionRun, StepExecution
│   │   │   ├── connection.py       # ConnectionConfig (Fernet-encrypted)
│   │   │   └── api_product.py      # Phase 8: APIProduct, APIPlan
│   │   └── db/
│   │       ├── base.py             # SQLAlchemy engine + session
│   │       └── migrations/         # Alembic revisions
│   └── tests/
│       ├── unit/
│       ├── integration/            # requires real Postgres
│       └── connectors/
├── frontend/                       # Phase 5 — React + TypeScript + Vite
├── docker-compose.yml
├── Makefile                        # make dev, test, lint, typecheck, migrate
├── Analysis/                       # existing design docs
└── mw-plan.md                      # this file
```

---

## 4. Connector Framework Architecture

The centrepiece of the entire platform. Every connector — built-in, community, or polyglot sidecar — implements the same 6-method interface. The framework handles encryption, pooling, OAuth refresh, config validation, and UI form generation automatically.

### Class hierarchy

```
BaseConnector (ABC — all connectors must subclass this)
├── SourceMixin     adds read() and read_batch()
└── SinkMixin       adds write() and write_batch()

Implementations:
FileConnector(BaseConnector, SourceMixin, SinkMixin)         ← reference impl
SalesforceConnector(BaseConnector, SourceMixin, SinkMixin)   ← OAuth2 pattern
S3Connector(BaseConnector, SourceMixin, SinkMixin)
PostgresConnector(BaseConnector, SourceMixin, SinkMixin)
RestApiConnector(BaseConnector, SourceMixin, SinkMixin)
```

### The 6-method contract

```python
class BaseConnector(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ConnectorMetadata: ...
    # ConnectorMetadata declares: connector_id, label, family, auth_type,
    # operations, connection_schema (JSON Schema → UI auto-generates config form)

    @abstractmethod
    def test_connection(self, handle: ConnectionHandle) -> bool: ...
    # Called by "Test connection" button in UI

    @abstractmethod
    def introspect_objects(self, handle) -> list[ObjectSchema]: ...
    # List tables / files / objects → shown in the source browser

    @abstractmethod
    def introspect_columns(self, handle, object_name: str) -> list[ColumnSchema]: ...
    # List fields for an object → drives visual mapper autocomplete

class SourceMixin:
    @abstractmethod
    def read(self, handle, config: ReadConfig) -> pd.DataFrame: ...

    def read_batch(self, handle, config) -> Iterator[pd.DataFrame]:
        yield self.read(handle, config)  # override for pagination

class SinkMixin:
    @abstractmethod
    def write(self, df, handle, config: WriteConfig) -> WriteResult: ...

    def write_batch(self, iterator, handle, config) -> WriteResult:
        return self.write(pd.concat(list(iterator)), handle, config)
```

### What the framework provides for free

| Feature | Implementation |
|---|---|
| Fernet encryption | All secrets encrypted at rest; decrypted only at runtime |
| TTL connection pooling | Connections reused for 180s (configurable) |
| OAuth2 token refresh | ConnectionManager calls refresh 60s before expiry, transparent to connector |
| Config validation | metadata.connection_schema is JSON Schema; framework validates before calling connector |
| UI forms auto-generated | Canvas reads connection_schema and renders config panel — no frontend code per connector |
| Retry + error wrapping | RateLimitError and NetworkError auto-retried with exponential backoff |
| sample() default | Base class calls read() with limit=10; override for efficiency |
| Polyglot protocol | Java/Go/Node.js connectors via 6 HTTP endpoints — framework calls them identically |

### Community connector registration (Workato/Boomi plugin pattern)

```toml
# pyproject.toml — one line registers any connector
[project.entry-points."sangam_mw.connectors"]
salesforce = "sangam_mw.connectors.salesforce:SalesforceConnector"

# Community package (pip install sangam-mw-kafka):
[project.entry-points."sangam_mw.connectors"]
kafka = "sangam_mw_kafka:KafkaConnector"
# ConnectorRegistry scans entry-points at startup. Connector appears in canvas palette.
```

### Auth types

```python
class AuthType(Enum):
    NONE             = "none"
    API_KEY          = "api_key"
    BASIC            = "basic"
    OAUTH2           = "oauth2"
    SERVICE_ACCOUNT  = "service_account"
```

### Polyglot HTTP sidecar (Java/Go/Node.js connectors)

Any language can implement a connector by exposing 6 HTTP endpoints:

```
POST /test      → { ok: bool }
POST /objects   → [{ name, kind }]
POST /columns   → [{ name, type }]
POST /read      → { rows: [...] }
POST /write     → { rows_written: int }
POST /sample    → { rows: [...] }
```

Register in YAML:
```yaml
connector_id: db2
runtime:
  type: http_sidecar
  command: ["java", "-jar", "connectors/db2.jar"]
  port: 9001
```

---

## 5. Transform Engine (4 layers)

Auto-selected by EngineRouter based on row count. Same YAML/SQL/Python syntax regardless of layer.

| Layer | Trigger | Technology | Use case |
|---|---|---|---|
| 1 — YAML declarative | Always available | Compiled to vectorised pandas ops | Rename, cast, date format, string ops. 25+ built-in functions. No eval(). |
| 2 — DuckDB SQL | TransformSQL step | DuckDB in-process | Full SQL: JOINs across step outputs, CTEs, window functions, PIVOT, UNNEST |
| 3 — Python pandas | TransformScript step | RestrictedPython sandbox | Custom logic, regex, numpy, any PyPI allowlisted package |
| 4 — PySpark | Auto at ≥500K rows | PySpark subprocess | Same YAML/SQL/Python spec, engine swaps transparently |

**Sandbox allowlist (Python):** pandas, numpy, re, json, datetime, math, collections  
**Sandbox blocklist:** os, subprocess, socket, open, __import__, eval, exec

**DuckDB key feature:** reads upstream step DataFrames as virtual tables by step ID:
```sql
-- JOIN two connector outputs in one SQL step:
SELECT a.customer_id, a.name, b.order_total
FROM extract_salesforce a
JOIN extract_postgres b ON a.customer_id = b.cust_id
WHERE b.order_total > 1000
```

---

## 6. Exception Handling

### Exception hierarchy

```
SangamMWException (carries: flow_id, run_id, step_id, timestamp)
├── ConnectorException
│   ├── RateLimitError          [RETRYABLE] exponential backoff 30s/60s/120s
│   ├── NetworkError            [RETRYABLE] transient
│   ├── AuthenticationError     [FATAL] never retry
│   ├── ConnectorValidationError [CAUGHT AT DEPLOY]
│   └── DataReadError           [FATAL]
├── TransformException
│   ├── TransformSyntaxError    [CAUGHT AT DEPLOY]
│   ├── DataTypeError           [ROW-LEVEL] skip or dead-letter
│   └── TransformMemoryError    [AUTO-PROMOTED to PySpark]
└── FlowException
    ├── FlowValidationError     [BLOCKED AT DEPLOY]
    ├── FlowTimeoutError        [FATAL]
    └── FlowAbortedError        [FATAL]
```

### Two-tier exception model

- **GlobalException node** — flow-level catch-all. Fires if any unhandled error reaches flow scope.
- **ComponentException node** — per-step override with custom retry policy and dead-letter config.

### Row-level error modes

| Mode | on_row_error | Behaviour |
|---|---|---|
| Fail all | `fail` | One bad row stops the entire flow |
| Skip and log | `skip_and_log` | Bad rows skipped and counted |
| Dead letter | `dead_letter` | Bad rows written to dead-letter sink with original data + error |
| Default value | `default` | Substitute configured default on cast error |

**error_threshold** — pairs with `skip_and_log` / `dead_letter`. Fails the flow if more than N% of rows error even in skip/dead-letter mode.

### Validate at deploy time (pre-flight)

All of these are checked before the first run. Deploy is blocked on any failure.

| Check | What |
|---|---|
| DAG validation | Cycles, unknown depends_on refs |
| Connection test | connector.test_connection() for each named connection |
| Schema introspection | Verify referenced objects/tables exist |
| SOQL explain | Salesforce explain API — validates SOQL without running |
| SQL parse | DuckDB EXPLAIN — syntax + unknown column names |
| Python compile | py_compile — syntax errors before first run |
| Transform spec | Source field names exist in upstream step schema |

---

## 7. Flow Engine — All 19 Node Types

### Trigger nodes (start a flow)
| Node | Description |
|---|---|
| Scheduler | Cron or interval trigger (APScheduler) |
| WebhookTrigger | Inbound HTTP POST with HMAC signature verification |
| StreamingTrigger | Kafka topic / SQS queue — per-message execution at low latency |
| EventTrigger | Generic event bus subscription |

### Data nodes
| Node | Description |
|---|---|
| ConnectorRead | Read from any source connector |
| ConnectorWrite | Write to any sink connector |

### Transform nodes
| Node | Description |
|---|---|
| TransformMap | YAML declarative field mapper (rename/cast/format) |
| TransformFilter | Drop rows by expression |
| TransformSQL | DuckDB SQL — full SQL including JOINs across step outputs |
| TransformScript | Python pandas (RestrictedPython sandbox) |

### Control flow nodes
| Node | Description |
|---|---|
| Router | Branch to 2+ paths on a condition expression |
| Merge | Rejoin parallel branches (wait-all or first-wins) |
| Iterator | For Each — execute sub-graph once per record |
| SubFlow | Call another flow as a step (callable flows) |

### Utility nodes
| Node | Description |
|---|---|
| SetVariable | Store a value in flow execution context |
| LookupTable | Embedded key→value reference data (no connector needed) |
| Approval | Human-in-the-loop Slack/Teams gate — flow pauses until approved/rejected |
| Notification | Send Slack / email / Teams message as a step |
| Logger | Emit structured audit event |
| SyncEndpoint | Expose flow as a synchronous request-response API endpoint |

### Exception nodes
| Node | Description |
|---|---|
| GlobalException | Flow-level catch-all handler |
| ComponentException | Per-node retry policy + dead-letter config |

### Canvas utilities (non-executing)
| Node | Description |
|---|---|
| StickyNote | Documentation annotation on the canvas |
| Start / End | Visual markers for flow boundaries |

---

## 8. Monitoring & Executions

Built across Phase 4 (data model + SSE stream), Phase 5 (UI), and Phase 7 (metrics + alerting).

### Execution data model

```
ExecutionRun
  run_id, flow_id, trigger_type, status, started_at, ended_at,
  rows_processed, rows_failed, rows_written

StepExecution
  step_id, step_type, status, duration_ms,
  rows_in, rows_out, rows_failed, error_type, error_message

ExecutionEvent (append-only)
  Structured JSON log event per lifecycle transition
```

### Run status lifecycle

```
PENDING → RUNNING → SUCCESS
                 → FAILED
                 → TIMED_OUT
                 → CANCELLED

Per step: PENDING → RUNNING → SUCCESS | FAILED | RETRYING | SKIPPED
```

### APIs

```
POST /execute               Trigger async run → returns run_id
POST /execute/sync          Trigger sync run → returns result in response body
POST /validate              Pre-flight validate a flow definition
POST /preview               Run with limit=50, return sample output
GET  /runs/{id}             Run status + step summary
GET  /runs/{id}/stream      SSE stream — one event per step lifecycle change
GET  /runs/{id}/steps/{s}/data   Sample output rows for a step
GET  /runs/{id}/dead-letter      Failed rows with original data + error
POST /runs/{id}/dead-letter/reprocess  Re-inject failed rows
POST /runs/{id}/replay           Re-run any historical run
```

### SSE event shape (canvas subscribes to this for live animation)

```json
{
  "event": "step_completed",
  "run_id": "run_20260921_abc123",
  "flow_id": "salesforce-to-s3",
  "step_id": "extract_salesforce",
  "step_type": "connector_read",
  "status": "SUCCESS",
  "duration_ms": 1840,
  "rows_out": 8412,
  "timestamp": "2026-09-21T02:03:14Z"
}
```

### Phase 7 Prometheus metrics

```
sangam_mw_runs_total{flow_id, status}
sangam_mw_run_duration_seconds{flow_id}        histogram
sangam_mw_rows_processed_total{flow_id, step_id}
sangam_mw_rows_failed_total{flow_id, step_id}
sangam_mw_connector_duration_seconds{connector_id, operation}   histogram
```

SLA alerting: fire if run duration > threshold, error rate > 5%, or row count drops > 20% vs 7-day average.

---

## 9. Phase Plan

### Phase 0 — Project Foundation (Weeks 1–2)

- `sangam-mw/` repo with `backend/` + `frontend/` layout
- `pyproject.toml` (hatch), module layout: `connectors/ transforms/ engine/ api/ models/ db/ cli/`
- Core Pydantic v2 models — ConnectionConfig, FlowDefinition, ExecutionRun, WriteResult, ObjectSchema, ColumnSchema
- SQLAlchemy 2 async engine + Alembic migrations + initial schema
- Google OAuth2 + JWT auth (`authlib` + `python-jose`)
- Docker Compose — FastAPI, Postgres, LocalStack (S3 mock)
- GitHub Actions CI — ruff, mypy, pytest (PRs blocked until green)
- Makefile — `make dev`, `make test`, `make lint`, `make typecheck`, `make migrate`
- `CONTRIBUTING.md` — connector author guide, test requirements, entry-point pattern

---

### Phase 1 — Connector Framework + File Connector (Weeks 2–5)

**Most critical phase. All other phases depend on this.**

- `BaseConnector` ABC — 4 abstract methods
- `ConnectorMetadata` — JSON Schema for connection / read / write config
- `SourceMixin` + `SinkMixin` with default batch implementations
- `AuthType` and `OperationType` enums
- Auth handlers — `OAuth2Handler` (token refresh + PKCE), `APIKeyHandler`, `BasicAuthHandler`, `ServiceAccountHandler`
- `ConnectionManager` — Fernet encryption, TTL pooling (180s default), OAuth refresh 60s before expiry
- `ConnectorRegistry` — scans `sangam_mw.connectors` entry-points at startup
- Error taxonomy — `ConnectorException` hierarchy: `RateLimitError` (retryable), `AuthenticationError` (fatal), `NetworkError` (retryable)
- `FileConnector` — CSV / JSON / Parquet / Excel. **Proves BaseConnector + SourceMixin + SinkMixin end-to-end.**
- CLI — `sangam connector list`, `sangam connector test <id>`, `sangam connector preview <id> <object>`
- Tests — 100% coverage on framework core; FileConnector integration tests against real files

---

### Phase 2 — Reference Connectors (Weeks 5–9)

Five connectors that prove every auth type and every operation pattern.

| Connector | Auth | Key implementation |
|---|---|---|
| `file` | NONE | CSV/JSON/Parquet/Excel — reference impl from Phase 1 |
| `salesforce` | OAUTH2 | SOQL mode + Object browser mode; pagination via nextRecordsUrl; upsert by external ID |
| `aws-s3` | SERVICE_ACCOUNT | boto3; multi-format; prefix listing as introspect_objects |
| `postgres` | BASIC + SSL | SQLAlchemy; full schema introspection; INSERT / UPSERT / REPLACE |
| `rest-api` | API_KEY / BEARER | Generic HTTP; configurable pagination (cursor / offset / link header) |

---

### Phase 3 — Transform Engine (Weeks 9–12)

- `FieldMapper` — YAML field spec compiles to vectorised pandas ops. 25+ built-in functions. No eval().
- `DuckDBEngine` — in-process; reads DataFrames as virtual tables named by step ID. Full SQL.
- `PythonSandbox` — RestrictedPython; allowlist: pandas/numpy/re/json/datetime/math; blocklist: os/subprocess/socket/open
- `EngineRouter` — auto-selects `PandasEngine` (< 500K rows) or `SparkEngine` (≥ 500K)
- `SparkEngine` — subprocess isolation; YAML → Spark column ops; SQL → Spark SQL; Python → mapInPandas UDF
- Deploy-time validators — `validate_sql()` (DuckDB EXPLAIN), `validate_python()` (py_compile), `validate_yaml_fields()` (schema check)

---

### Phase 4 — Flow Engine & Orchestration (Weeks 12–17)

- `FlowSchema` (Pydantic v2) — validates flow YAML at load time
- `DAGParser` — Kahn's topological sort; cycle detection; disconnected graph detection
- `FlowExecutor` — ExecutionContext (output cache, variable store), step orchestration, structured JSON events
- `FlowValidator` — pre-flight: connection test, SOQL explain, SQL parse, Python compile, schema field check
- `ExecutionRun` + `StepExecution` DB models (Alembic migration)
- `ExecutionEvent` append-only log
- SSE stream endpoint (`GET /runs/{id}/stream`)
- Scheduler — APScheduler cron + interval triggers, persisted to Postgres
- `POST /execute/sync` — synchronous request-response mode
- Webhook trigger endpoint — HMAC signature verification, auto-generated URL per flow
- Streaming trigger — Kafka topic / SQS queue as per-message flow trigger
- All 19 step types implemented (see Section 7)
- FastAPI engine API — all routes wired

---

### Phase 5 — Visual Canvas & Designer UI (Weeks 17–24)

- React + TypeScript + Vite project (`frontend/`)
- React Flow canvas — all 19 node types, left palette drag-to-canvas, edge drawing, pan/zoom
- `+` button on edges — insert transform node between any two existing steps
- Node config panels — right panel per node type, Config + Exception tabs, auto-generated from connector metadata JSON Schema
- **Visual Mapper** — drag source fields to target fields, pick transform function per connection, generates YAML automatically
- **Monaco Editor** — SQL (DuckDB dialect) + Python inline editors, column autocomplete from upstream step schema
- Live preview — "Preview 50 rows" button calls `/preview` API, shows input → output diff
- Code view toggle — switch between canvas and raw YAML (bidirectional sync)
- Run history — execution list, step waterfall timeline (Gantt), structured log viewer
- **Interactive debugger** — step-through mode, pause after each node, inspect live data in right panel, breakpoints
- Live canvas animation — nodes pulse while running, turn green/red via SSE subscription
- **Per-message document tracking** — store every record with correlation ID; search by any field value across all historical runs; replay individual records
- **Schema registry** — central schema store; shared schemas; drift detection when connector schema changes
- Dead-letter browser — view failed rows, original data, error reason, reprocess button
- Connection manager UI — add/test/delete named connections, secrets via Fernet

---

### Phase 6 — Connector Ecosystem (Weeks 24–30)

**Connectors by family:**

| Family | Connectors |
|---|---|
| Messaging | Kafka, SQS/SNS, RabbitMQ, Azure Service Bus, Google Pub/Sub |
| Analytics / DWH | Snowflake, BigQuery, Redshift, ClickHouse, DuckDB (server), Databricks |
| NoSQL / Graph / Cache | MongoDB, Elasticsearch, Redis, Neo4j, Cosmos DB, Cassandra |
| SaaS CRM/ERP | HubSpot, Zendesk, ServiceNow, Workday, Shopify, Stripe |
| Communication | Slack, Teams, SendGrid |
| AI / Vector | Pinecone, Weaviate, Qdrant, OpenAI, Anthropic, Bedrock |

**Platform features:**
- Community connector SDK — docs, `sangam-mw-cookiecutter` scaffolds a new package in 30 seconds
- Polyglot HTTP sidecar — Java/Go/Node.js connectors via 6 HTTP endpoints, full documentation
- **Integration template marketplace** — pre-built flow templates for common use cases (Salesforce→S3, REST API→Postgres, Kafka→BigQuery). Community-submittable. One-click import and configure.
- **Managed on-prem agent (OPA)** — lightweight Docker image running behind a firewall, polls control plane for flow assignments, executes flows locally. No inbound ports required. Cloud UI manages agent health and assignments.

---

### Phase 7 — Enterprise & Production (Weeks 30–38)

- **RBAC** — roles: admin / developer / viewer / operator. Per-flow access control.
- **SAML 2.0 / SSO** — Okta, Azure AD, Google Workspace IdP. SCIM for user provisioning.
- Multi-environment — dev → staging → prod promotion. Connection aliases per env.
- Git-native deployment — `sangam deploy` pushes flows from local git. PR review for flow changes. Rollback via git revert.
- **Tamper-evident audit log** — append-only, hash-chained entries. Export to SIEM. Satisfies SOC 2 Type II, HIPAA, ISO 27001.
- **Data lineage & dependency graph** — visual map of which flows read from which connectors, which fields are produced by which transforms. Impact analysis before connector changes.
- **Flow testing framework** — `sangam test flows/my-flow.yaml`. Define test cases with mock connector outputs. Assert on output schema / row count / field values. Runs in CI (GitHub Actions, GitLab CI). No real connections needed.
- **Mock connector** — declare in test config, returns fixed rows. Test transform and routing logic without hitting live systems.
- **AI-generated flow from description** — type "sync Salesforce opportunities updated in the last 24h to Snowflake" → Claude API generates flow YAML. Developer reviews and deploys.
- **AI-assisted field mapping** — Claude API suggests field mappings in the visual mapper based on source + target schema similarity.
- Prometheus `/metrics` endpoint — key metrics: runs total, duration histogram, rows processed/failed, connector latency
- Grafana dashboard template — shipped as JSON, importable into any Grafana
- SLA alerting — duration threshold, error rate > 5%, row count anomaly > 20% vs 7-day average
- HashiCorp Vault integration — alternative to Fernet for enterprise secret management
- Dead-letter bulk reprocessing + run replay

---

### Phase 8 — API Management & Gateway (Weeks 38+)

The feature that unlocks API-first enterprise buyers (MuleSoft's core product). Turns SangamMW into an API platform, not just an integration platform.

- **API Gateway** — route inbound HTTP to flows. Rate limiting (per consumer, per plan), API key auth, JWT validation, IP allowlisting.
- **API Products & Plans** — bundle endpoints into a product. Define plans (Free: 100 req/day, Pro: 10K req/day). Metered usage tracking.
- **Consumer API key management** — external consumers self-register, get scoped API keys.
- **Developer portal** — browse published APIs, try in browser (Swagger UI), register for access, view usage dashboard. Auto-generated from OAS spec.
- **OAS 3.0 / AsyncAPI designer** — design-first entry point: define API contract in OAS, generate flow skeleton that implements it. Canvas can also export OAS spec.
- **API analytics** — requests/sec, error rate, latency p50/p95/p99, top consumers, quota usage. Per-endpoint and per-consumer views.
- **Request/response transformation** — transform inbound payload before flow, transform flow output before HTTP response. Same YAML mapper + DuckDB engine.
- **Mock API endpoint** — serve canned response from OAS spec without a real flow. Design-first development.
- **Webhook outbound management** — register consumer webhook URLs, retry failed deliveries, view delivery history.

API product definition (YAML):
```yaml
api_product:
  name: Customer Data API
  version: v1
  base_path: /api/v1
  endpoints:
    - path: /customers
      method: GET
      flow: salesforce-customer-query
      auth: api_key
      rate_limit: { plan: pro, requests_per_minute: 100 }
    - path: /customers/{id}/orders
      method: GET
      flow: order-lookup-flow
      auth: jwt
      cache_ttl_seconds: 60
  plans:
    - { name: free, requests_per_day: 1000 }
    - { name: pro,  requests_per_day: 50000 }
  portal:
    enabled: true
    oas_spec: specs/customer-api.yaml
```

---

## 10. Competitive Positioning

### Where we win

| Differentiator | Why it matters |
|---|---|
| **SQL + Python transforms** | DataWeave, XSLT, Groovy — nobody on data teams knows these. SQL and pandas — everyone does. Zero learning curve. |
| **DuckDB in-process SQL** | JOIN across two connector outputs in a single SQL step. No data movement, no JDBC round-trip. No competitor has this. |
| **Auto-scale pandas → PySpark** | Same spec at 500K+ rows. Competitors cap at in-memory or require a separate "batch job" model. |
| **Open source + pip install** | All four competitors are proprietary SaaS. Lowest contribution barrier of any middleware platform. |
| **Git-native (flows as YAML)** | Flows in git — PR review, git blame, rollback, CI/CD. No other platform does this natively. |
| **Dead-letter first-class** | Native sink, error_threshold, UI browser, reprocess API. Competitors require you to build this yourself. |
| **Validate at deploy** | SQL/SOQL/Python/DAG all validated before first run. Catches 80% of errors before production. |
| **Polyglot connector protocol** | Java/Go/Node.js via 6 HTTP endpoints. Competitors only accept their own SDK (Java for Boomi and MuleSoft). |
| **AI-native from day 1** | Claude for field mapping suggestions and flow generation from description. Designed in, not bolted on. |

### Known gaps (not planned)

| Gap | Notes |
|---|---|
| **B2B / EDI** | X12, EDIFACT, AS2, Trading Partner Management — not in plan. Loses supply-chain/logistics RFPs. |

---

## 11. Infrastructure Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Metadata database | **PostgreSQL only** | Single engine for local dev + production. Docker Compose includes Postgres. |
| Platform auth | **JWT + Google OAuth2** | authlib + python-jose. No password management. SAML/SSO added in Phase 7. |
| Repo layout | **Single repo** | `backend/` + `frontend/`. One git repo, shared CI. |
| License | **MIT** | Open source, maximum community adoption. |
| Python version | **3.11+** | `match` statements, tomllib, ExceptionGroup, type annotation improvements. |

---

## 12. Phase Summary Table

| Phase | Name | Weeks | Key deliverable | Status |
|---|---|---|---|---|
| 0 | Foundation | 1–2 | Repo, Postgres, auth, CI, Docker Compose | ✅ DONE |
| 1 | Connector Framework | 2–5 | BaseConnector + FileConnector — the pattern everything follows | ✅ DONE |
| 2 | Reference Connectors | 5–9 | Salesforce, S3, Postgres, REST API — one per auth type | ✅ DONE |
| 3 | Transform Engine | 9–12 | YAML + DuckDB SQL + Python sandbox + PySpark auto-scale | ✅ DONE |
| 4 | Flow Engine | 12–17 | DAG executor, all 19 node types, streaming triggers, SSE | ✅ DONE |
| 5 | Visual Canvas | 17–24 | React Flow canvas, visual mapper, Monaco, debugger, document tracking | ✅ DONE |
| 6 | Ecosystem | 24–30 | 9 new connectors, template marketplace, community SDK | ✅ DONE |
| 7 | Enterprise | 30–38 | RBAC, SAML, audit log, lineage, flow testing, AI flow gen | ✅ DONE |
| 8 | API Gateway | 38+ | API gateway, developer portal, OAS designer, rate limiting, analytics | ✅ DONE |
| 9 | Production Hardening | 40+ | Observability, OTEL, multi-env config, SCIM, health checks, deploy CLI | ✅ DONE |
| 10 | Test Suite | 40+ | 272/272 tests passing across all phases | ✅ DONE |
| 11 | Frontend Completion | 40+ | Auth/login UI, dashboard, gateway management, admin portal, live run monitor | ✅ DONE |

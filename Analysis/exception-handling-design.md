# Exception Handling Design
**Date:** 2026-09-21  
**Status:** ARCHITECTURE DECISION

---

## Core Design Principles

1. **Validate at deploy time** — syntax errors, unknown step references, DAG cycles, invalid SOQL are all caught during `validate()` before the first run. Runtime exceptions are for genuinely runtime problems (network failures, data type mismatches).

2. **Retryable vs non-retryable is automatic** — the exception type determines retry behaviour, not the user's config. `RateLimitError` always retries. `AuthenticationError` never does.

3. **Nothing is silently lost** — dead-letter sink for row-level errors. Every error emits a structured JSON event.

4. **Row-level error mode is configurable** — flow author decides whether a single bad row fails the whole flow, is skipped, or goes to a dead-letter sink.

---

## Exception Hierarchy

```
SangamMWException (base — always carries: flow_id, run_id, step_id, timestamp)
│
├── ConnectorException
│   ├── RateLimitError          [RETRYABLE] exp backoff 30s/60s/120s
│   ├── NetworkError            [RETRYABLE] transient — connection reset, DNS, SSL
│   ├── AuthenticationError     [FATAL] wrong credentials, revoked token, expired refresh
│   ├── ConnectorValidationError [CAUGHT AT DEPLOY] invalid SOQL, unknown object
│   └── DataReadError           [FATAL] connector returned unreadable data
│
├── TransformException
│   ├── TransformSyntaxError    [CAUGHT AT DEPLOY] SQL syntax error, Python syntax error
│   ├── DataTypeError           [ROW-LEVEL] cast "abc" to float — skip or dead-letter
│   └── TransformMemoryError    [AUTO-PROMOTED] pandas OOM → EngineRouter retries on Spark
│
└── FlowException
    ├── FlowValidationError     [BLOCKED AT DEPLOY] DAG cycle, unknown step ref
    ├── FlowTimeoutError        [FATAL] exceeded timeout_seconds
    └── FlowAbortedError        [FATAL] manual cancellation
```

---

## Retry Policy

### Connector-level retries (per step)

```yaml
- id: extract_salesforce
  type: connector_read
  retries: 3                               # max retry attempts
  retry_delay: exponential                 # exponential | fixed
  # exponential: 30s → 60s → 120s
  retry_on: [rate_limit, timeout, network_error]
  timeout_seconds: 300
```

### Built-in retry for known patterns

| Pattern | Behaviour |
|---|---|
| Salesforce HTTP 429 | Reads `Retry-After` header; waits exactly that long |
| AWS S3 throttle | Exponential backoff (AWS SDK default — pass-through) |
| Network reset | Immediate retry once, then exponential |
| OAuth token expired | Token refresh happens transparently (not an error, handled by ConnectionManager) |

### Retry does NOT apply to:

- `AuthenticationError` — wrong credentials will still be wrong in 30 seconds
- `ConnectorValidationError` — bad SOQL will still be bad syntax
- `TransformSyntaxError` — invalid SQL/Python will still fail

### TransformMemoryError: special case

When pandas runs out of memory on a large dataset, the EngineRouter auto-promotes to PySpark and retries the step — without raising to the flow or alerting the user. Logged as a `WARN` event, not an error.

---

## Row-Level Error Modes

Configured per transform or write step via `on_row_error`.

| Mode | `on_row_error` | Behaviour | When to use |
|---|---|---|---|
| Fail all | `fail` | One bad row stops the entire flow | Financial, compliance — partial load is worse than no load |
| Skip and log | `skip_and_log` | Bad rows skipped, counted, logged | Analytics — a few bad records are tolerable |
| Dead letter | `dead_letter` | Bad rows (with original data + error reason) written to dead-letter sink | Production — nothing lost, investigated and reprocessed later |
| Default value | `default` | On cast error, substitute configured default (null, 0, "unknown") | Tolerant pipelines |

**`error_threshold`** — pairs with `skip_and_log` and `dead_letter`. If more than this percentage of rows error, the engine treats the batch as fatal regardless of row-level mode. Prevents silently losing data while technically "succeeding".

```yaml
- id: transform_step
  type: transform_map
  on_row_error: dead_letter
  error_threshold: "5%"    # fail if >5% of rows error
```

---

## Dead Letter Sink

Failed rows are written to a configurable connector with original data + error metadata:

```yaml
dead_letter:
  connector: aws-s3
  connection: prod-aws
  config:
    bucket: sangam-error-records
    key: "errors/{{ flow_id }}/{{ run_id }}/{{ execution_date }}.json"
    format: json
```

Each dead-letter record contains:
```json
{
  "flow_id": "salesforce-opps-to-s3",
  "run_id": "run_20260921_020000_abc123",
  "step_id": "reshape_fields",
  "row_index": 347,
  "error_type": "DataTypeError",
  "error_message": "Cannot cast 'N/A' to float for field Amount",
  "original_row": { "Id": "0060U000...", "Amount": "N/A", "CloseDate": "2026-09-21" },
  "timestamp": "2026-09-21T02:03:14Z"
}
```

---

## Flow-Level Error Handler

```yaml
error_handler:
  on_failure: notify_and_stop     # notify_and_stop | retry_flow | continue
  retries: 1                      # flow-level retry — re-runs from failed step
  notifications:
    - type: slack
      connection: prod-slack
      channel: "#data-alerts"
      message: |
        Flow *{{ flow_id }}* failed at step {{ failed_step_id }}
        Error: {{ error_message }}
        Rows processed: {{ rows_processed }} / {{ rows_total }}
        Run: {{ run_id }}
    - type: email
      connection: prod-smtp
      to: ["data-oncall@company.com"]
```

### on_failure options

| Value | Behaviour |
|---|---|
| `notify_and_stop` | Alert and mark run FAILED. No rerun. |
| `retry_flow` | Retry the whole flow (only for flows triggered by scheduler). Respects `retries` count. |
| `continue` | On failure of a non-critical step, skip it and continue. Only valid for steps marked `optional: true`. |

---

## Structured Error Event (always emitted)

Every exception emits a structured JSON log event regardless of retry/dead-letter behaviour:

```json
{
  "event": "step_failed",
  "level": "ERROR",
  "flow_id": "salesforce-opps-to-s3",
  "run_id": "run_20260921_020000_abc123",
  "step_id": "load_to_s3",
  "step_type": "connector_write",
  "error_type": "ConnectorException.NetworkError",
  "error_message": "Connection reset by peer after 47 retries",
  "retryable": true,
  "retry_count": 3,
  "rows_processed_before_failure": 1244,
  "rows_total": 1247,
  "duration_ms": 18420,
  "timestamp": "2026-09-21T02:03:41Z"
}
```

This event feeds:
- `structlog` → stdout (local), Cloud Logging (GCP), CloudWatch (AWS)
- Alerting (Slack/email via `error_handler`)
- The Run History UI (run status, step timeline, error details)

---

## Validation at Deploy Time

Before any flow is deployed (`sangam deploy flows/my-flow.yaml`), the engine runs a full pre-flight check:

| Check | What it does |
|---|---|
| **DAG validation** | Detects cycles, unknown `depends_on` references |
| **Connection test** | Calls `connector.test_connection()` for each named connection |
| **Schema introspection** | Calls `connector.introspect_objects()` to validate that referenced objects/tables exist |
| **SOQL explain** | Calls Salesforce explain API to validate SOQL syntax without running the query |
| **SQL parse** | Parses DuckDB SQL with `EXPLAIN` — detects syntax errors, unknown column names |
| **Python compile** | Compiles Python script step with `py_compile` — detects syntax errors before first run |
| **Transform spec** | Validates each field spec — checks that referenced `source` fields exist in the upstream step's schema |

The deploy is blocked if any check fails. Errors are shown inline with the offending line.

---

## Summary: What Makes This Different

| Tool | Error handling |
|---|---|
| **MuleSoft** | Try-Catch scope (Java-style), On Error Continue / On Error Propagate — powerful but verbose |
| **Boomi** | Process Exception shape — similar concept but GUI-only config |
| **Airflow** | `retries` + `retry_delay` on operators, no row-level error modes |
| **Our middleware** | Retryable/non-retryable split automatic; dead-letter native; error_threshold; validate at deploy; structured events |

The key differentiator: **dead-letter sink is first-class** (not an afterthought), and **validate at deploy** catches most errors before they ever cause a production failure.

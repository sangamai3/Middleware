# Scenario Design: Salesforce → Transform → AWS S3
**Date:** 2026-09-21  
**Purpose:** Reference design showing exactly how a Salesforce-to-AWS integration is expressed and executed in SangamMW

---

## 1. The Flow Definition (what the developer writes)

A Flow is a YAML file stored in Git. This is the complete definition for this scenario:

```yaml
# flows/salesforce-opportunities-to-s3.yaml

flow_id: salesforce-opps-to-s3
name: Salesforce Won Opportunities → S3 Parquet
version: 1.0.0
description: Extract closed-won opportunities from Salesforce daily, transform, write to S3 as Parquet

trigger:
  type: scheduler
  cron: "0 2 * * *"          # daily at 02:00 UTC
  timezone: UTC

connections:
  salesforce: prod-salesforce  # named connection from the Connection Store
  aws: prod-aws-s3

steps:

  - id: extract_opportunities
    type: connector_read
    connector: salesforce
    connection: "{{ connections.salesforce }}"
    config:
      mode: soql
      soql: >
        SELECT Id, Name, Amount, CloseDate, StageName,
               AccountId, Account.Name, OwnerId, Owner.Name,
               CreatedDate, LastModifiedDate
        FROM Opportunity
        WHERE CloseDate = THIS_MONTH
      batch_size: 2000          # Salesforce max per page; connector paginates automatically

  - id: filter_closed_won
    type: transform_filter
    depends_on: [extract_opportunities]
    config:
      expression: "StageName == 'Closed Won'"   # safe column expression, not eval()

  - id: reshape_fields
    type: transform_map
    depends_on: [filter_closed_won]
    config:
      fields:
        - source: Id
          target: opportunity_id

        - source: Name
          target: opportunity_name

        - source: Amount
          target: deal_value_usd
          transform: round(2)

        - source: CloseDate
          target: close_date
          transform: format_date("%Y-%m-%d")

        - source: Account.Name        # nested Salesforce relationship field
          target: account_name

        - source: Owner.Name
          target: owner_name

        - source: CreatedDate
          target: created_at
          transform: parse_datetime_iso

        # fields not listed here are dropped by default
        # set drop_unlisted: false to keep all source fields

      drop_unlisted: true

  - id: load_to_s3
    type: connector_write
    connector: aws-s3
    connection: "{{ connections.aws }}"
    depends_on: [reshape_fields]
    config:
      bucket: sangam-data-lake
      key: "salesforce/opportunities/{{ execution_date }}/closed_won.parquet"
      format: parquet
      write_mode: overwrite        # overwrite | append | partition
      compression: snappy

error_handler:
  on_failure: notify_and_stop
  notifications:
    - type: slack
      connection: prod-slack
      channel: "#data-alerts"
      message: |
        Flow *{{ flow_id }}* failed
        Step: {{ failed_step_id }}
        Error: {{ error_message }}
        Run: {{ run_id }}

execution:
  engine: auto               # auto | pandas | spark
  # auto: chooses pandas for <500K rows, spark for larger
  timeout_seconds: 1800
  retries: 2
  retry_delay_seconds: 60
```

---

## 2. What Happens at Runtime (step by step)

### Step 0 — Trigger fires

The scheduler fires at 02:00 UTC. The `FlowExecutor` receives the trigger event and starts a new execution run:

```python
run = ExecutionRun(
    run_id="run_20260921_020000_abc123",
    flow_id="salesforce-opps-to-s3",
    triggered_by="scheduler",
    started_at=datetime.utcnow(),
    execution_date="2026-09-21",
)
```

The `ExecutionContext` is initialised — it holds:
- The run metadata
- A reference to the Connection Store (for resolving named connections)
- A step-output cache (DataFrames keyed by step ID)
- The structured logger

### Step 1 — `extract_opportunities` (ConnectorReadStep)

```python
# FlowExecutor calls:
connector = registry.get("salesforce")        # SalesforceConnector instance
handle = connection_manager.get("prod-salesforce")  # from Connection Store

df = connector.read(handle, config={
    "mode": "soql",
    "soql": "SELECT Id, Name, Amount, ... FROM Opportunity WHERE CloseDate = THIS_MONTH",
    "batch_size": 2000,
})
```

**Inside `SalesforceConnector.read()`:**
1. Check `handle.token_expiry` → call `refresh_if_needed()` → get fresh OAuth token
2. POST `/services/data/v59.0/query?q=<SOQL>` to Salesforce instance URL
3. Response contains `records` (up to 2,000) + optional `nextRecordsUrl`
4. Loop: GET `nextRecordsUrl` until `done == true`
5. Flatten nested relationship fields (`Account.Name` → `Account__Name` internally, remapped in Step 3)
6. Return `pd.DataFrame(all_records)` — **~8,400 rows** in this example

**Output saved:** `ctx.outputs["extract_opportunities"] = df  # shape: (8400, 11)`

---

### Step 2 — `filter_closed_won` (FilterTransformStep)

```python
input_df = ctx.outputs["extract_opportunities"]

# Safe column expression — uses pandas .query() for simple comparisons
# Falls back to .apply(lambda) for complex multi-column logic
output_df = input_df.query("StageName == 'Closed Won'")
```

**Output saved:** `ctx.outputs["filter_closed_won"] = output_df  # shape: (1247, 11)`

The row count drops from 8,400 to 1,247 — only the won deals pass through.

---

### Step 3 — `reshape_fields` (MapTransformStep)

```python
input_df = ctx.outputs["filter_closed_won"]

# MapTransformStep processes the field spec declaratively:
mapper = FieldMapper(config.fields, drop_unlisted=True)
output_df = mapper.apply(input_df)
```

**Inside `FieldMapper.apply()`:**

| Source field | Target field | Transform applied |
|---|---|---|
| `Id` | `opportunity_id` | rename only |
| `Name` | `opportunity_name` | rename only |
| `Amount` | `deal_value_usd` | `round(2)` → `pd.to_numeric().round(2)` |
| `CloseDate` | `close_date` | `format_date("%Y-%m-%d")` → `pd.to_datetime().dt.strftime(...)` |
| `Account.Name` | `account_name` | rename (dotted path → flat column) |
| `Owner.Name` | `owner_name` | rename |
| `CreatedDate` | `created_at` | `parse_datetime_iso` → `pd.to_datetime(..., utc=True)` |
| `AccountId`, `OwnerId`, `StageName`, `LastModifiedDate` | *(dropped)* | `drop_unlisted: true` removes these |

**Output saved:** `ctx.outputs["reshape_fields"] = output_df  # shape: (1247, 7)`

---

### Step 4 — `load_to_s3` (ConnectorWriteStep)

```python
input_df = ctx.outputs["reshape_fields"]
handle = connection_manager.get("prod-aws-s3")

connector = registry.get("aws-s3")       # S3Connector instance

result = connector.write(input_df, handle, config={
    "bucket": "sangam-data-lake",
    "key": "salesforce/opportunities/2026-09-21/closed_won.parquet",  # template resolved
    "format": "parquet",
    "write_mode": "overwrite",
    "compression": "snappy",
})
```

**Inside `S3Connector.write()`:**
1. Resolve key template: `{{ execution_date }}` → `"2026-09-21"`
2. Serialize DataFrame: `df.to_parquet(buffer, engine="pyarrow", compression="snappy")`
3. `boto3.client("s3").put_object(Bucket=..., Key=..., Body=buffer.getvalue())`
4. Return `WriteResult(rows_written=1247, destination="s3://sangam-data-lake/salesforce/opportunities/2026-09-21/closed_won.parquet", bytes_written=142_080)`

---

### Step 5 — Execution Complete

`FlowExecutor` marks the run complete:
```python
run.status = "completed"
run.finished_at = datetime.utcnow()
run.rows_processed = 1247
run.steps_completed = 4
```

Structured log emitted:
```json
{
  "event": "flow_completed",
  "flow_id": "salesforce-opps-to-s3",
  "run_id": "run_20260921_020000_abc123",
  "duration_ms": 18420,
  "rows_in": 8400,
  "rows_out": 1247,
  "destination": "s3://sangam-data-lake/salesforce/opportunities/2026-09-21/closed_won.parquet"
}
```

---

## 3. The Class Hierarchy Behind This Flow

```
BaseConnector (ABC)
├── SalesforceConnector
│     read(handle, config) → DataFrame
│       - SOQL mode: paginate nextRecordsUrl until done=true
│       - Object mode: describe() then bulk query
│       - Token refresh: calls auth.refresh_if_needed() before each page
│
└── S3Connector (extends FileStorageConnector)
      write(df, handle, config) → WriteResult
        - Serialize DataFrame to bytes (parquet/csv/json/ndjson)
        - Resolve key template
        - boto3 put_object

BaseTransformStep (ABC)
├── FilterTransformStep
│     execute(ctx) → DataFrame
│       - Simple expressions: df.query(expr)  ← fast pandas native
│       - Complex expressions: df.apply(safe_eval(expr))
│
└── MapTransformStep
      execute(ctx) → DataFrame
        - FieldMapper.apply(df) — iterates field specs
        - Built-in transforms: round, format_date, parse_datetime, uppercase,
          lowercase, to_str, parse_json, split, join
        - Custom: inline Python lambda in YAML (sandboxed via RestrictedPython)

ConnectionManager
  get(name) → ConnectionHandle
    - Looks up named connection from Connection Store
    - Decrypts secrets (Fernet)
    - Returns pooled or fresh connection
    - Checks token expiry; refreshes OAuth tokens transparently

FlowExecutor
  execute(flow, trigger_payload) → RunResult
    - Builds ExecutionContext
    - Topo-sorts steps (Kahn's algorithm)
    - Executes each step; stores output in ctx.outputs[step_id]
    - On exception: logs, runs error_handler, re-raises
    - EngineRouter: picks PandasEngine (<500K rows) or SparkEngine (larger)
```

---

## 4. Alternate AWS Targets (same flow, different Step 4)

### → AWS DynamoDB (upsert records)
```yaml
  - id: load_to_dynamodb
    type: connector_write
    connector: dynamodb
    connection: prod-aws
    depends_on: [reshape_fields]
    config:
      table: salesforce_opportunities
      write_mode: upsert
      key_field: opportunity_id    # partition key
```

### → Amazon Redshift (bulk insert)
```yaml
  - id: load_to_redshift
    type: connector_write
    connector: redshift
    connection: prod-redshift
    depends_on: [reshape_fields]
    config:
      table: dw.salesforce_opportunities
      write_mode: upsert
      key_columns: [opportunity_id]
      staging_bucket: sangam-redshift-staging   # uses COPY command via S3
```

### → Amazon SQS (publish each record as a message)
```yaml
  - id: publish_to_sqs
    type: connector_write
    connector: sqs
    connection: prod-aws
    depends_on: [reshape_fields]
    config:
      queue_url: https://sqs.us-east-1.amazonaws.com/123456/opp-events
      message_format: json          # each row → one SQS message
      batch_size: 10                # SQS max 10 messages per send_message_batch call
```

---

## 5. Variant: SOQL vs. Full Object Mode

### SOQL mode (developer writes the query)
```yaml
config:
  mode: soql
  soql: "SELECT Id, Name, Amount FROM Opportunity WHERE CloseDate = THIS_MONTH AND Amount > 10000"
```
Use when: you need specific fields, WHERE filters, related object fields (`Account.Name`), or ORDER BY.

### Object mode (middleware introspects the schema)
```yaml
config:
  mode: object
  object: Opportunity
  fields: [Id, Name, Amount, CloseDate, StageName]   # omit = all fields
  filters:
    - field: CloseDate
      operator: equals
      value: THIS_MONTH
```
Use when: non-technical users configure the flow via a UI. The middleware calls `describe(Opportunity)` to show available fields, then builds the SOQL internally.

The visual Flow Designer (future) would expose Object mode — users pick the object from a dropdown, tick fields, and set filter values. SOQL mode is the power-user / developer path.

---

## 6. Error Scenarios and How They're Handled

| Failure point | What happens |
|---|---|
| Salesforce OAuth token expired | `refresh_if_needed()` fires before each request; transparent to the flow |
| Salesforce API rate limit (HTTP 429) | `SalesforceConnector` retries with exponential backoff (3× with 30s/60s/120s delays) |
| SOQL invalid syntax | Raised as `ConnectorValidationError` at deploy time (pre-flight `explain()` call), not at runtime |
| Filter expression invalid | Caught at `FlowExecutor.validate()` before execution starts |
| S3 write permission denied | `ConnectorWriteError` raised; error_handler fires Slack notification |
| S3 bucket does not exist | Same as above |
| Partial failure mid-pagination | Salesforce connector is transactional per-page; on error, raises with page number in context so retry can resume |
| Flow timeout (1800s exceeded) | `FlowExecutor` cancels in-flight step; marks run `timed_out`; Slack alert |

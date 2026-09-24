# QA scenarios — File Source & File Target

**Scope:** Local **File** connector (`connector_read` / `connector_write`) via Flow Designer wizard, API execution, and Postgres-backed flow persistence.

**Formats in scope:** CSV, JSON, Parquet, Excel (`.xlsx`).

---

## Prerequisites

| Item | Detail |
|------|--------|
| Stack | API on `8100`, UI on `5173`, Postgres up (`make dev-db` or `SANGAM_POSTGRES=auto`) |
| Login | Valid dev user / token |
| Test folders | Two writable directories on the machine running the **API** (paths are server-local, not browser-local) |
| Sample data | See [Test data setup](#test-data-setup) |

**Important:** `base_path` is resolved on the **backend host**. Use paths the API process can read/write (e.g. `/tmp/sangam-qa/in` and `/tmp/sangam-qa/out`).

---

## Test data setup

Create once before manual runs:

```bash
mkdir -p /tmp/sangam-qa/in /tmp/sangam-qa/out
```

**`in/orders_a.csv`**

```csv
id,region,amount
1,US,100
2,EU,200
```

**`in/orders_b.csv`**

```csv
id,region,amount
3,US,150
4,APAC,90
```

**`in/customers.json`** (optional — format tests)

```json
[{"id":1,"name":"Alice"}]
```

Keep `out/` empty at the start of each scenario group that writes files.

---

## What to test (summary matrix)

| Area | What we are proving |
|------|---------------------|
| **Connection** | `base_path`, `create_if_not_exists`, Test connection, boolean config not sent as strings |
| **Source object** | Default `*.csv`, single file, glob merge, unsupported pattern / missing files |
| **Target object** | Default `output.csv`, replace vs append (CSV), custom name |
| **Write per source** | One output file per matched source; stem preserved; needs glob on source |
| **Timestamp** | `add_timestamp` + `timestamp_format` on single file and per-source writes |
| **Output format** | Target `output_format` when write-per-source (e.g. CSV → JSON) |
| **Flow designer** | Wizard steps, Save / autosave, refresh & API restart still list flows |
| **Run** | Validate, Run, row counts / step status, files on disk match expectation |
| **Negative** | Bad path, no matching glob, write without upstream, invalid timestamp format fallback |

---

## Scenario 1 — Happy path: single CSV → single CSV

**Goal:** Minimal File Source → File Target pipeline.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Flows → **New flow** | Designer opens |
| 2 | Add **Source** (File), wizard: `base_path` = `/tmp/sangam-qa/in`, **Test & continue** | Success; continue enabled |
| 3 | Source step: object = `orders_a.csv` (or accept default only if testing defaults in S2) | Value saved on node |
| 4 | Add **Target** (File), `base_path` = `/tmp/sangam-qa/out`, `create_if_not_exists` = on | Test connection OK |
| 5 | Target: object = `result.csv`, mode = **replace** | — |
| 6 | Connect Source → Target | Edge present |
| 7 | **Validate** | Valid (warnings OK if documented) |
| 8 | **Run** | Run completes; source step success; target success |
| 9 | Inspect `/tmp/sangam-qa/out/result.csv` | 2 data rows (+ header); columns `id,region,amount` |

**Pass:** File exists, row count = source, no step failed.

---

## Scenario 2 — Source defaults and glob

**Goal:** Default pattern `*.csv` and multi-file read.

### 2a — Default source pattern

| Step | Action | Expected |
|------|--------|----------|
| 1 | New File Source, path `/tmp/sangam-qa/in` | On objects step, field shows or applies **`*.csv`** |
| 2 | Continue without typing a pattern | Config stores `*.csv` (check after Save or re-open node) |
| 3 | Run to Target `merged.csv` (single file target) | Read merges **orders_a** + **orders_b** → **4 rows** in `merged.csv` |

### 2b — Explicit glob

| Step | Action | Expected |
|------|--------|----------|
| 1 | Source object = `orders_*.csv` | Same 4 rows when run to single target |

### 2c — No matching files

| Step | Action | Expected |
|------|--------|----------|
| 1 | Source object = `missing_*.csv` | **Run fails** on read with clear error (no files matched) |

**Pass:** Defaults behave; glob merges; empty glob fails loudly.

---

## Scenario 3 — Target defaults

**Goal:** Default output name when user leaves target file blank.

| Step | Action | Expected |
|------|--------|----------|
| 1 | File Target, **write per source** off, clear output name | UI shows hint / placeholder `output.csv` |
| 2 | Continue / Save | Resolved object = `output.csv` |
| 3 | Run flow | `/tmp/sangam-qa/out/output.csv` created |

**Pass:** No manual filename required for single-file target.

---

## Scenario 4 — Write one file per source file

**Goal:** `write_per_source` + glob source.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Source: `*.csv` or `orders_*.csv` | — |
| 2 | Target: enable **Write one file per source file** | Output name field hidden or not required |
| 3 | Run | `out/orders_a.csv` and `out/orders_b.csv` (or same names as sources) |
| 4 | Row counts | Each file has its original row count (2 each) |

**Pass:** Two files, not one merged file.

---

## Scenario 5 — Append timestamp

**Goal:** Filename suffix from `add_timestamp` and optional format.

### 5a — Single output file

| Step | Action | Expected |
|------|--------|----------|
| 1 | Target: `report.csv`, **Append timestamp** on | — |
| 2 | Run twice | Two files like `report_YYYYMMDD_HHMMSS.csv` (exact pattern per preset) |
| 3 | Change **timestamp format** preset (or custom strftime) | New runs use new pattern; invalid format falls back safely (no crash) |

### 5b — Write per source + timestamp

| Step | Action | Expected |
|------|--------|----------|
| 1 | Source glob + target write per source + timestamp | Files like `orders_a_<ts>.csv`, `orders_b_<ts>.csv` |

**Pass:** Timestamp appears in filename; reruns do not overwrite prior timestamped files.

---

## Scenario 6 — Output format conversion (write per source)

**Goal:** `output_format` on target when preserving per-source names.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Source: `*.csv` | — |
| 2 | Target: write per source, `output_format` = `.json` (or JSON option in UI) | — |
| 3 | Run | `orders_a.json`, `orders_b.json` valid JSON arrays |
| 4 | Content | Same logical rows as CSV sources |

**Pass:** Extension and format match selection.

---

## Scenario 7 — Append mode (CSV only)

**Goal:** Connector `mode: append` on target.

| Step | Action | Expected |
|------|--------|----------|
| 1 | First run: target `append_test.csv`, mode **replace**, source `orders_a.csv` | 2 rows |
| 2 | Second run: same target, mode **append**, source `orders_b.csv` | File has **4 rows** (2 + 2) |

**Pass:** Append concatenates; replace overwrites.

---

## Scenario 8 — Connection edge cases

| Step | Action | Expected |
|------|--------|----------|
| 1 | `base_path` does not exist, `create_if_not_exists` = **false** | Test connection **fails** |
| 2 | Same path, `create_if_not_exists` = **true** | Test creates dir and **succeeds** |
| 3 | Path is a file, not directory | Test **fails** |
| 4 | Toggle wizard options that are booleans | No API error like `'true' is not of type 'boolean'` |

**Pass:** Connection test matches real filesystem rules; types normalized.

---

## Scenario 9 — Flow persistence & designer UX

**Goal:** Flows and config survive refresh and API restart.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Build flow with File source + target, wait for autosave or click **Save** | Dirty indicator clears |
| 2 | Browser **hard refresh** | Same flow id loads; nodes and `base_path` / object config intact |
| 3 | Flows list page | Flow still listed |
| 4 | Restart API (not wiping Postgres volume) | List + open designer still works |
| 5 | Navigate away without save after edit | `beforeunload` warning OR autosave within ~2s |

**Pass:** No “empty flows list” after refresh when Postgres is up; config not lost.

---

## Scenario 10 — Validate vs Run

| Step | Action | Expected |
|------|--------|----------|
| 1 | Flow with only Source, no target | Validate may warn; Run should fail or no-op target appropriately |
| 2 | Target not connected to source | Validate error or run failure (no upstream) |
| 3 | Valid connected flow | Validate **Valid**; Run succeeds |

**Pass:** Validate catches structural issues before or during run.

---

## Scenario 11 — Optional formats (smoke)

Repeat **Scenario 1** with:

| Source file | Target file | Note |
|-------------|-------------|------|
| `customers.json` | `out.json` | JSON roundtrip |
| Parquet created via pytest or pandas | `.parquet` | If sample added under `in/` |
| `.xlsx` | `.xlsx` | If sample added |

**Pass:** Each supported suffix reads and writes without format error.

---

## Scenario 12 — Read options (API / advanced config)

If exposed in UI or via step config JSON:

| Option | Test | Expected |
|--------|------|----------|
| `limit` | `limit: 1` on read | Output has 1 row |
| `fields` | `fields: ["id"]` | Only `id` column |
| `filter` | `filter: "amount > 100"` | Subset of rows |

**Pass:** Matches pandas behavior on file connector.

---

## Regression checklist (quick smoke)

Use before release or after connector/wizard changes:

- [ ] Test connection on file source with real `base_path`
- [ ] Source default `*.csv` and run merges multiple CSVs
- [ ] Target default `output.csv` when name empty
- [ ] Write per source produces N files for N glob matches
- [ ] Timestamp creates new filename per run
- [ ] Save flow → refresh → config still there
- [ ] API restart → flows list not empty (Postgres)

---

## Automated coverage (reference)

| Layer | Location |
|-------|----------|
| File connector unit tests | `backend/tests/unit/test_file_connector.py` |
| Filename timestamp | `backend/tests/unit/test_filename_timestamp.py` |
| Flow validation warnings | `backend/tests/unit/test_validation.py` (file object warnings) |
| Full stack | Scenarios above (manual) |

```bash
cd backend && pytest tests/unit/test_file_connector.py tests/unit/test_filename_timestamp.py -q
```

---

## Result log (fill when executing)

| Run | Date | Tester | Scenarios | Result | Notes |
|-----|------|--------|-----------|--------|-------|
| 1 | | | 1–10 | | |

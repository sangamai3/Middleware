# Transformation Engine Design
**Date:** 2026-09-21  
**Status:** DRAFT — key architecture decision

---

## The Core Question

Every integration requires data transformation. The question is: what language do you use to express it, and why?

Enterprise tools made different bets:
- **MuleSoft** → DataWeave (custom functional language, Java ecosystem, very powerful, nobody knows it on day 1)
- **Boomi** → Visual mapper + Groovy/JavaScript scripts
- **SAP CPI** → Graphical mapper + XSLT + Groovy
- **Informatica** → Visual mapper + SQL + Python/Spark

None of them converged on a single answer because **different transformations have different natural expressions**. Neither should we.

---

## Our Answer: A Four-Layer Stack

```
┌───────────────────────────────────────────────────────┐
│  Layer 1 — Declarative YAML          no-code          │
│  rename · cast · format · concat · drop               │
├───────────────────────────────────────────────────────┤
│  Layer 2 — DuckDB SQL                low-code         │
│  aggregate · window · join · CTE · PIVOT              │
├───────────────────────────────────────────────────────┤
│  Layer 3 — Python (pandas)           code             │
│  arbitrary logic · ML · regex · any PyPI lib          │
├───────────────────────────────────────────────────────┤
│  Layer 4 — PySpark                   auto-scaled      │
│  same YAML/SQL/Python, engine swaps at 500K rows      │
└───────────────────────────────────────────────────────┘
```

**Rule:** use the simplest layer that solves the problem. Layers compose — a flow can use all four in sequence.

---

## Layer 1 — Declarative YAML

### What it is
A field-level mapping specification written in YAML. No code. Describes *what* to do, not *how*.

### Syntax

```yaml
- type: transform_map
  fields:
    # Rename only
    - source: Id
      target: opportunity_id

    # Rename + type cast
    - source: Amount
      target: deal_value_usd
      cast: float
      round: 2

    # Date formatting
    - source: CloseDate
      target: close_date
      format_date: "%Y-%m-%d"

    # Nested relationship field (Salesforce Account.Name)
    - source: Account.Name
      target: account_name

    # Computed field — concatenate two source columns
    - target: full_name
      concat: [FirstName, " ", LastName]

    # Conditional / coalesce
    - source: Phone
      target: contact_phone
      coalesce: [Phone, MobilePhone, HomePhone]  # first non-null wins

    # Static literal
    - target: source_system
      value: "salesforce"

    # PII masking
    - source: Email
      target: email_masked
      mask: email     # → j***@example.com

  drop_unlisted: true   # fields not listed above are dropped
```

### Built-in transform functions

| Category | Functions |
|---|---|
| String | `uppercase`, `lowercase`, `trim`, `strip`, `replace(old,new)`, `regex_extract(pattern)`, `regex_replace(pattern,repl)`, `split(delim)`, `join(delim)`, `substring(start,end)`, `to_str`, `parse_json`, `to_json`, `hash(algo)` |
| Numeric | `round(n)`, `floor`, `ceil`, `abs`, `to_int`, `to_float`, `format_number(pattern)` |
| Date | `format_date(fmt)`, `parse_date(fmt)`, `parse_datetime_iso`, `to_epoch`, `from_epoch`, `date_add(days)`, `truncate_to(unit)` |
| Boolean | `to_bool`, `negate` |
| Null | `coalesce([fields])`, `if_null(default)`, `drop_if_null` |
| Masking | `mask(type)` — email, phone, ssn, cc; `redact`, `tokenize` |
| Structural | `flatten_nested`, `explode(field)`, `nest(fields, into)` |
| Conditional | `case(conditions, values, default)` |

### Why YAML for Layer 1?

1. **UI designer-friendly** — the visual canvas can render a YAML field spec as a drag-and-drop mapper without any code parsing
2. **Auditable** — a business analyst can read the YAML and understand exactly what data changes happen, without understanding Python
3. **Safe** — no arbitrary execution; the engine compiles the spec to vectorised pandas operations (`.rename()`, `.astype()`, `.dt.strftime()`, etc.)
4. **Optimisable** — the engine can reorder operations, push them down into connector queries (e.g. compile a field list into a Salesforce SOQL SELECT), or batch them
5. **Searchable** — grep for a field name across all flows to find every place it's transformed
6. **Covers ~70% of real-world integration transforms** — most are "rename this, cast that, format a date, drop PII"

### How it compiles

```python
# YAML spec:
#   - source: Amount
#     target: deal_value_usd
#     cast: float
#     round: 2

# Compiled to:
df = df.rename(columns={"Amount": "deal_value_usd"})
df["deal_value_usd"] = pd.to_numeric(df["deal_value_usd"], errors="coerce").round(2)
```

No `eval()`, no `exec()`. Pure pandas operations, fully type-safe.

---

## Layer 2 — SQL (DuckDB, in-process)

### What it is
Full SQL running against the DataFrame in-process using DuckDB. No server. No Docker. DuckDB reads a pandas DataFrame as a virtual table called `input`.

### Why DuckDB and not pandas or Spark SQL?

| | pandas | DuckDB | Spark SQL |
|---|---|---|---|
| Server required | No | **No** | Yes (JVM) |
| Setup | None | **None** | Heavy |
| Full SQL (window fns, CTEs) | No | **Yes** | Yes |
| PIVOT, UNNEST | No | **Yes** | Partial |
| Performance vs pandas | baseline | **10–100× faster** for aggregations | Varies |
| Reads DataFrame directly | N/A | **Yes** — zero copy | No — needs Spark session |
| Known by data engineers | SQL via SQLAlchemy | **Plain SQL** | Spark SQL dialect |
| Multi-step JOIN | No | **Yes** — JOIN across step outputs | Yes |

DuckDB wins on every axis that matters for a middleware. It was built exactly for this: in-process analytical SQL on DataFrames.

### Syntax

```yaml
- type: transform_sql
  sql: |
    SELECT
      account_name,
      owner_name,
      SUM(deal_value_usd)                           AS total_value,
      COUNT(*)                                       AS deal_count,
      AVG(deal_value_usd)                            AS avg_deal_size,
      RANK() OVER (ORDER BY SUM(deal_value_usd) DESC) AS revenue_rank,
      CURRENT_DATE                                   AS report_date
    FROM input
    GROUP BY account_name, owner_name
    HAVING SUM(deal_value_usd) > 50000
    ORDER BY total_value DESC
```

### Advanced capabilities

#### JOIN across two upstream steps
```yaml
- id: enrich_with_account_data
  type: transform_sql
  depends_on: [filter_closed_won, load_accounts]   # two input DataFrames
  sql: |
    SELECT
      o.opportunity_id,
      o.deal_value_usd,
      a.industry,
      a.employee_count,
      a.headquarters_country
    FROM filter_closed_won o
    LEFT JOIN load_accounts a ON o.account_id = a.account_id
```

Step IDs become table names in the SQL. Clean, readable, no boilerplate.

#### Window functions
```yaml
sql: |
  SELECT
    *,
    SUM(deal_value_usd) OVER (PARTITION BY account_name) AS account_total,
    ROW_NUMBER()        OVER (PARTITION BY account_name ORDER BY close_date DESC) AS rn
  FROM input
```

#### UNNEST (explode arrays)
```yaml
# If a Salesforce record has a list field (e.g. Tags: ["hot", "Q3", "renewal"])
sql: |
  SELECT opportunity_id, UNNEST(tags) AS tag
  FROM input
```

#### PIVOT
```yaml
sql: |
  PIVOT input
  ON stage_name
  USING SUM(deal_value_usd)
  GROUP BY account_name
```

### Why SQL is the right choice for Layer 2

- **Universal literacy** — SQL is the most widely known data language in the world. Every data engineer, analyst, and backend developer knows it. DataWeave is not.
- **Expressiveness** — window functions, CTEs, aggregations, and JOINs express most analytical transforms in 5–20 lines that would take 50+ lines of pandas
- **No dialect fragmentation** — DuckDB SQL is standard SQL. The same query runs on pandas engine (DuckDB) and Spark engine (compiled to Spark SQL). No learning two dialects.
- **Debuggable** — you can copy the SQL into DBeaver or a notebook and run it against sample data to verify before deploying

---

## Layer 3 — Python Script Step

### What it is
A Python function that takes a DataFrame and returns a DataFrame. Full pandas, numpy, and any installed PyPI library available.

### Syntax

```yaml
- type: transform_script
  language: python
  code: |
    import pandas as pd
    import numpy as np

    def transform(df: pd.DataFrame) -> pd.DataFrame:
        # Deal tier classification
        df["deal_tier"] = pd.cut(
            df["deal_value_usd"],
            bins=[0, 10_000, 50_000, 200_000, float("inf")],
            labels=["small", "medium", "large", "enterprise"],
        )

        # Normalise company name (remove "Inc.", "LLC", etc.)
        df["account_name_clean"] = (
            df["account_name"]
            .str.replace(r"\b(Inc|LLC|Ltd|Corp|Co)\.?\b", "", regex=True)
            .str.strip()
        )

        # Flag stale deals (close date >90 days ago)
        df["is_stale"] = (
            pd.Timestamp.now() - pd.to_datetime(df["close_date"])
        ).dt.days > 90

        return df
```

### Why Python?

- **Data engineers already know it** — pandas is the lingua franca of the data world. Nobody needs to learn a new language.
- **Full ecosystem** — scikit-learn for ML scoring, regex for text processing, Faker for test data, pyarrow for binary formats — all available.
- **DataWeave is not Python** — MuleSoft's DataWeave is the most powerful transform language in enterprise iPaaS, but it is Java-ecosystem-only. Our target audience is Python-first data engineers.
- **Familiar tooling** — Python functions are easy to unit-test locally with `pytest` before deploying to the middleware.

### Safety: RestrictedPython sandbox

The script runs inside a [RestrictedPython](https://restrictedpython.readthedocs.io/) sandbox:

```python
# What IS allowed in the sandbox:
import pandas       # ✓
import numpy        # ✓
import re           # ✓
import json         # ✓
import datetime     # ✓
# any library in sangam_mw.config.allowed_imports  # ✓

# What is NOT allowed:
import os           # ✗ — file system access blocked
import subprocess   # ✗ — process execution blocked
import socket       # ✗ — network access blocked
open("file.txt")    # ✗ — file I/O blocked
__import__("os")    # ✗ — dynamic imports blocked
```

Network and file I/O inside a script step are always blocked. If a transform needs to call an external service, that's a connector step, not a transform step.

### When to use Layer 3 instead of Layer 2

Use Python when:
- Complex business rules that are hard to express in SQL (multi-step conditional logic, string normalisation, fuzzy matching)
- ML model inference (`model.predict(df)`)
- Geospatial calculations (`shapely`, `geopandas`)
- Custom PII detection or masking beyond built-in functions
- Calling Python-native libraries with no SQL equivalent (`faker`, `phonenumbers`, `dateutil`)

---

## Layer 4 — PySpark (auto-scaled)

### What it is
The same YAML declarative / SQL / Python transforms, running on PySpark when data volume exceeds the `auto` threshold (default 500K rows). The developer writes nothing different.

### How the engine router works

```python
class EngineRouter:
    def select(self, df: pd.DataFrame, config: FlowConfig) -> PipelineEngine:
        if config.execution.engine == "spark":
            return SparkEngine()
        if config.execution.engine == "pandas":
            return PandasEngine()

        # "auto" — decide based on row count
        row_count = len(df)
        if row_count > config.execution.spark_threshold:  # default: 500_000
            return SparkEngine()
        return PandasEngine()
```

### What changes at the Spark layer

| Transform type | pandas engine | spark engine |
|---|---|---|
| `transform_map` (YAML) | Compiled to `df.rename()`, `df.astype()`, etc. | Compiled to `df.withColumnRenamed()`, `df.withColumn(F.cast(...))`, etc. |
| `transform_filter` (YAML) | `df.query(expr)` | `df.filter(F.expr(expr))` |
| `transform_sql` (DuckDB SQL) | DuckDB runs in-process against pandas DF | SQL compiled to Spark SQL, runs on SparkSession |
| `transform_script` (Python) | Direct function call on DataFrame | Function wrapped as a Spark `mapInPandas` UDF |

The developer never sees this. The YAML is the same. The SQL is the same. The Python function signature is the same — `transform(df: pd.DataFrame) → pd.DataFrame` — Spark calls it via `mapInPandas`.

---

## Full Example: All Four Layers in One Flow

```yaml
# Salesforce → enrich → score → S3

steps:

  # Layer 1: simple field rename and cast
  - id: clean_fields
    type: transform_map
    depends_on: [extract_salesforce]
    config:
      fields:
        - source: Amount
          target: deal_value_usd
          cast: float
          round: 2
        - source: CloseDate
          target: close_date
          format_date: "%Y-%m-%d"
        - source: Account.Name
          target: account_name
      drop_unlisted: false   # keep all other fields too

  # Layer 2: SQL aggregation and window function
  - id: rank_by_account
    type: transform_sql
    depends_on: [clean_fields]
    sql: |
      SELECT
        *,
        SUM(deal_value_usd) OVER (PARTITION BY account_name) AS account_total,
        RANK() OVER (PARTITION BY account_name ORDER BY deal_value_usd DESC) AS rank_in_account
      FROM input

  # Layer 3: Python for ML scoring
  - id: score_deals
    type: transform_script
    depends_on: [rank_by_account]
    language: python
    code: |
      import pandas as pd
      import pickle, base64

      MODEL_B64 = "{{ secrets.deal_score_model }}"   # model stored as base64 secret

      def transform(df: pd.DataFrame) -> pd.DataFrame:
          model = pickle.loads(base64.b64decode(MODEL_B64))
          features = df[["deal_value_usd", "account_total", "rank_in_account"]]
          df["churn_risk_score"] = model.predict_proba(features)[:, 1].round(3)
          return df

  # Write to S3
  - id: load_to_s3
    type: connector_write
    connector: aws-s3
    depends_on: [score_deals]
    config:
      bucket: sangam-data-lake
      key: "salesforce/scored_opps/{{ execution_date }}/data.parquet"
      format: parquet
```

---

## Why NOT Just Use Python Everywhere?

This is a fair question. The answer is that Python scripts are the **worst** choice for simple transforms:

| Concern | YAML | SQL | Python script |
|---|---|---|---|
| Can UI designer render it visually? | ✓ Yes | Partial | ✗ No |
| Can non-engineer read it? | ✓ Yes | ✓ Yes | ✗ No |
| Can engine optimise it (push-down)? | ✓ Yes | ✓ Yes | ✗ No |
| Security surface area | Minimal | Minimal | **Requires sandboxing** |
| Debuggable in isolation? | ✓ | ✓ DuckDB CLI | ✓ pytest |
| Works across pandas + Spark unchanged? | ✓ | ✓ | ✓ (via mapInPandas) |

A rename-and-cast that takes 3 lines of YAML should not require a Python function. That said, Python as the escape hatch is infinitely better than MuleSoft's DataWeave for our Python-first audience — no new language to learn.

---

## Why NOT DataWeave?

DataWeave is genuinely the most powerful transform language in enterprise iPaaS. But:

1. **It is Java-ecosystem-only** — requires a running Mule runtime (JVM). Cannot run standalone in a Python process.
2. **Nobody knows it on day 1** — it has a unique syntax that takes weeks to learn. Our users already know Python and SQL.
3. **Not open source** — proprietary to MuleSoft/Salesforce. No community contributions.
4. **Overkill for most transforms** — 90% of DataWeave usage is field mapping + type coercion. YAML handles that.
5. **We cover the remaining 10% with Python scripts**, which is more flexible anyway.

---

## Summary: Language Selection Guide

| Situation | Use |
|---|---|
| Rename fields, cast types, format dates, drop columns | **YAML `transform_map`** |
| Filter rows by column values | **YAML `transform_filter`** |
| Group by, aggregate (sum/count/avg), window functions | **SQL `transform_sql`** |
| JOIN two data sources | **SQL `transform_sql`** |
| PIVOT / UNNEST | **SQL `transform_sql`** |
| Complex conditional business logic | **Python `transform_script`** |
| ML model inference, fuzzy matching | **Python `transform_script`** |
| Custom PII masking | **Python `transform_script`** |
| >500K rows, any of the above | **PySpark (auto-selected, same syntax)** |

# Runtime Language Decision
**Date:** 2026-09-21  
**Status:** DECIDED  
**Decision:** Python (FastAPI) as core engine · Node.js/TypeScript for UI/frontend · Polyglot connector protocol for extensions

---

## The Question

Should the middleware runtime be written in Python, Node.js/TypeScript, or Java? Each has been used to build production middleware:

- **Java** — MuleSoft (Mule 4), Boomi (Atoms), SAP CPI (Apache Camel), Spring Integration
- **Node.js** — many lightweight iPaaS startups, Zapier's backend
- **Python** — Airflow, Prefect, Dagster, dbt (all built on Python)

---

## Why Python Wins for Our Core Engine

### 1. We already have it — 100% codebase reuse

Both eInsta and AgentStudio backend are Python (FastAPI). The connector logic, introspection engine, connection pooling, pipeline runner, and Fernet secrets store are all Python. Rewriting in Java or Node.js means throwing away months of working, tested code.

### 2. The data engineering world is Python

Our target audience — data engineers, platform engineers, AI teams — live in Python. They write pandas transforms, PySpark jobs, dbt models, and Prefect flows in Python every day.

- When a data engineer writes a custom transform, they reach for pandas.
- When they debug a connector, they pip install the driver and open a notebook.
- When they want ML scoring in a pipeline, they use scikit-learn.

None of this exists in Node.js. Java has Spark, but the data engineering community has largely moved to PySpark.

### 3. The AI/LLM ecosystem is Python-first

We want to be an AI-native middleware. Every major AI library is Python:

| Library | Language |
|---|---|
| Anthropic SDK | Python (first-class), TypeScript (second) |
| OpenAI SDK | Python (first-class) |
| LangChain | Python |
| LlamaIndex | Python |
| Hugging Face Transformers | Python |
| scikit-learn | Python |
| sentence-transformers | Python |
| Pinecone / Weaviate / Qdrant clients | Python (first-class) |

Building AI-native features in Java means wrapping Python subprocesses anyway. We skip that layer.

### 4. DuckDB — our SQL transform engine — is Python-native

DuckDB's in-process SQL engine integrates directly with pandas DataFrames:

```python
import duckdb
result_df = duckdb.query("SELECT account_name, SUM(amount) FROM df GROUP BY 1").df()
```

This works because DuckDB reads Python objects directly. There is no equivalent in Node.js (there is a Node.js DuckDB binding, but it does not read DataFrames — there are no DataFrames in Node.js). In Java, DuckDB runs via JNI with significant FFI overhead.

### 5. PySpark — our big-data engine — requires Python

PySpark *is* Python. The Spark job subprocess in eInsta is already Python. Forcing Spark through Java would mean writing Spark jobs in Scala/Java and proxying results, adding a translation layer that serves nobody.

### 6. FastAPI is genuinely fast enough

A common objection: "Python is slow." For a middleware doing I/O-bound work (database queries, HTTP calls, file reads), this is mostly irrelevant:

- FastAPI with uvicorn (asyncio) handles thousands of concurrent requests via async I/O
- The bottleneck in a connector is always the remote system (Salesforce API, PostgreSQL), not the Python process
- Where CPU matters (large transforms), we already offload to DuckDB (C++) or PySpark (JVM) — Python is just the orchestrator

For reference: Anthropic's API, Stripe's data pipelines, Airflow, Prefect, and dbt are all Python in production.

---

## Where Java Would Be Better (and what we do about it)

Java has two genuine advantages we can't ignore:

### JDBC — universal database connectivity

Java's JDBC has drivers for literally every database ever made. Some databases (SAP HANA, IBM DB2, Teradata, some mainframe connectors) have JDBC drivers but no Python driver, or the Python driver is unmaintained.

**Our solution:** The polyglot connector protocol (see below). A Java connector process wraps a JDBC connection and exposes it over HTTP. The core engine calls it like any other connector. No Java in the core.

### Enterprise SDK availability (SAP, Workday, Oracle)

Some enterprise vendors ship their primary SDK in Java. The SAP Java Connector (JCo) for RFC/BAPI calls is the canonical example — there is no official Python equivalent that handles all SAP IDoc types.

**Our solution:** Same — polyglot connector protocol. A Java sidecar wraps the SAP JCo library and exposes it as a connector endpoint. The middleware calls it over HTTP.

---

## Where Node.js Fits

Node.js/TypeScript is already doing its job in this project: **the frontend and code generation**.

AgentStudio's entire code generation engine — the 18 connector plugins, the Eta templates, the React wizard — is TypeScript. That stays TypeScript. Node.js is genuinely better than Python for:

- React/Vite frontend builds
- Streaming JSON to the browser
- Server-Side Rendering
- The visual flow canvas

**What Node.js cannot do:** data processing. There is no pandas in Node.js. There is no PySpark. There is no DuckDB DataFrame integration. A flow that processes 8,400 Salesforce records through three transforms cannot run in Node.js without either shipping the data to Python or re-implementing pandas in JavaScript. Neither makes sense.

---

## The Polyglot Connector Protocol

This is the key design that lets us say "Python core" without excluding Java or Node.js connector authors.

### Concept

Any language can implement a connector by exposing a simple HTTP API. The core engine calls it over localhost (or over the network for remote connectors). The connector process can be written in Java, Go, Rust, Node.js — anything that speaks HTTP.

### Connector HTTP API (the protocol every connector must implement)

```
POST /test          Test the connection → { ok: bool, error?: str }
POST /objects       List tables/collections → [{ name, kind, schema }]
POST /columns       List columns for an object → [{ name, type, nullable }]
POST /read          Read data → { rows: [...], next_cursor?: str }
POST /write         Write data → { rows_written: int }
POST /sample        Sample rows → { rows: [...] }
```

Every endpoint receives the connection config as the POST body. The connector process handles auth, pooling, and pagination internally.

### How a Java JDBC connector registers

```yaml
# connectors/jdbc-db2.yaml
connector_id: db2
label: IBM DB2
family: sql
kind: sql
runtime:
  type: http_sidecar
  command: ["java", "-jar", "connectors/db2-connector.jar"]
  port: 9001
  health_check: /health
```

On flow execution:
1. The core engine reads the connector config → sees `type: http_sidecar`
2. Starts the Java process on port 9001 (or uses a pre-running process)
3. Calls `POST http://localhost:9001/read` with the connection config
4. Gets back rows as JSON
5. Converts to DataFrame — same as any built-in connector

The Java jar handles all JDBC details. The core never touches Java.

### Protocol variants

| Type | Description | Use case |
|---|---|---|
| `builtin` | Python class in core repo | All 73 standard connectors |
| `http_sidecar` | External HTTP process, same machine | Java/Go/Rust connectors |
| `http_remote` | External HTTP process, remote URL | SaaS connector hosting |
| `plugin` | Python class via entry point (`pip install`) | Community Python connectors |

### Example: Node.js connector for a niche SaaS

```javascript
// A Node.js connector for some JavaScript-first SaaS with only a JS SDK
const express = require('express')
const { NicheClient } = require('niche-saas-js-sdk')

const app = express()
app.post('/read', async (req, res) => {
  const client = new NicheClient(req.body.api_key)
  const records = await client.getAll(req.body.object)
  res.json({ rows: records })
})
app.listen(9002)
```

Register it:
```yaml
connector_id: niche-saas
runtime:
  type: http_sidecar
  command: ["node", "connectors/niche-saas/index.js"]
  port: 9002
```

The core calls it identically to a built-in Python connector. The developer who wrote it never needed to learn Python.

---

## Architecture: Three Runtimes, One Platform

```
┌──────────────────────────────────────────────────────────────┐
│                    SangamMW Platform                          │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Python Core (FastAPI)                                  │ │
│  │                                                         │ │
│  │  • Flow execution engine      • Connector registry      │ │
│  │  • DAG orchestrator           • Connection manager      │ │
│  │  • Transform layers           • Secrets store           │ │
│  │    - YAML declarative         • Auth framework          │ │
│  │    - DuckDB SQL               • REST API                │ │
│  │    - pandas scripts           • Python SDK              │ │
│  │    - PySpark (subprocess)     • CLI                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│            ↑ HTTP / entry-point                               │
│  ┌──────────────────────┐    ┌───────────────────────────┐   │
│  │  Node.js / TypeScript│    │  Polyglot Connector       │   │
│  │  Frontend            │    │  Sidecars (optional)      │   │
│  │                      │    │                           │   │
│  │  • Visual flow canvas│    │  • Java (JDBC, SAP JCo)   │   │
│  │  • AgentStudio UI    │    │  • Go (high-perf connctrs)│   │
│  │  • Code generation   │    │  • Node.js (JS-SDK SaaS)  │   │
│  │  • Vite build        │    │  • Rust (custom binary)   │   │
│  └──────────────────────┘    └───────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

---

## Language Decision Summary

| Layer | Language | Why |
|---|---|---|
| Core engine | **Python 3.11+** | Data ecosystem, AI/ML, existing codebase, DuckDB, PySpark |
| Web framework | **FastAPI** | Async, Pydantic models, OpenAPI auto-generation, fastest Python framework |
| Pipeline engine (small) | **Python + DuckDB + pandas** | In-process, zero setup |
| Pipeline engine (large) | **PySpark via subprocess** | Subprocess isolation, existing eInsta runner |
| Type safety | **Pydantic v2 + mypy** | Pydantic for config/models, mypy for static checking |
| Visual designer | **React + TypeScript** | Existing AgentStudio frontend |
| Code generation | **TypeScript + Eta templates** | Existing AgentStudio engine |
| Built-in connectors | **Python** | Shared driver ecosystem |
| Community connectors | **Any language** | Polyglot connector protocol (HTTP sidecar) |
| CLI | **Python + Typer** | Single language, ship as PyPI binary via `pip install` |
| Tests | **pytest** | De facto standard for Python projects |

---

## What This Gives Us vs. Competition

| | MuleSoft | Boomi | Our middleware |
|---|---|---|---|
| Core language | Java | Java | **Python** |
| Transform language | DataWeave (custom) | Groovy/JS | **YAML + SQL + Python — everyone knows these** |
| Data engineer learning curve | High (DataWeave) | Medium (Groovy) | **Zero — it's Python and SQL** |
| AI/ML in transforms | Via Java SDK | Via Groovy | **Native — pandas, scikit-learn, any PyPI** |
| Big data | Spark via Java | Limited | **PySpark native** |
| Polyglot connectors | No | No | **Yes — Java/Go/Node.js via HTTP protocol** |
| Open source contribution barrier | Very high (Java, proprietary) | Closed source | **Low — `pip install`, familiar Python** |

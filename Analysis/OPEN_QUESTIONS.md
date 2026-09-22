# Open Questions — SangamMW Design Debates

This file tracks unresolved design decisions. Each question stays here until debated and resolved.  
When resolved, add the decision + rationale here, then carry it into the next version file.

---

## Format

```
### Q{N}: <title>
**Status:** OPEN | RESOLVED  
**Options:**  
**Resolved decision:** (fill when resolved)  
**Rationale:** (fill when resolved)  
```

---

## Architecture

### Q1: Library vs. Service (deployment model)
**Status:** OPEN  
**Context:** Should SangamMW be deployed as a standalone REST service (like AgentStudio's backend today), or as an importable Python library with no server required, or both?  
**Options:**
- A) **Service-first** — FastAPI server, clients call over HTTP. Easiest to polyglot-consume (JS, Java). Network boundary means secrets stay server-side. Adds latency and an extra process.
- B) **Library-first** — `pip install sangam-mw`, import directly. Zero latency, no server. Harder for non-Python clients. Secrets live in the caller's process.
- C) **Library + optional server** — library is the core; the server is a thin API wrapper around it. Most flexible but more surface area to maintain.  
**Resolved decision:**  
**Rationale:**

---

### Q2: PySpark — hard dependency or optional engine?
**Status:** OPEN  
**Context:** eInsta's pipeline engine requires PySpark (a 300MB+ install with Java dependency). Many users won't need Spark at all — they just want connectors.  
**Options:**
- A) **Hard dependency** — always install PySpark. Simple, one requirements set, always available. Heavy.
- B) **Optional extra** — `pip install sangam-mw[spark]`. Default engine is pandas-only. Spark only available if installed. Requires runtime `importlib` check.
- C) **Separate package** — `sangam-mw-spark` is a separate PyPI package that registers the `SparkEngine` via a plugin entry point. Cleanest separation, but more publishing overhead.  
**Resolved decision:**  
**Rationale:**

---

### Q3: Scope of v1.0 — connectors only vs. connectors + pipeline engine?
**Status:** OPEN  
**Context:** The pipeline engine (DAG, Spark, transforms) is substantial additional scope. Connectors alone already solve a real problem (AgentStudio's dependency).  
**Options:**
- A) **Connectors + auth + connection management only** for v1.0. Pipeline engine is v2.0. Faster to ship, narrower API surface to stabilise.
- B) **Full stack (connectors + pipeline engine)** in v1.0. More complete, but longer to ship.
- C) **Connectors in v1.0, pipeline engine behind a feature flag** — ship it but mark `@experimental`.  
**Resolved decision:**  
**Rationale:**

---

### Q4: Connection pooling strategy
**Status:** OPEN  
**Context:** AgentStudio uses a module-level dict with 180s TTL. This works in single-process but doesn't scale to multi-worker deployments (e.g. uvicorn with 4 workers — each worker has its own pool, no sharing).  
**Options:**
- A) **TTL dict, per-process** (current AgentStudio approach). Simple, zero dependencies, works fine for single-process.
- B) **SQLAlchemy connection pool** for SQL connectors (min/max pool size, connection validation). Standard approach for SQL; doesn't cover NoSQL/REST.
- C) **Per-driver pooling** — SQLAlchemy for SQL, motor for async MongoDB, redis-py's built-in pool for Redis, explicit pool for REST (httpx `AsyncClient` lifecycle). Most correct; most code.
- D) **External pool manager** — PgBouncer / ProxySQL for SQL at the infrastructure level. Move pooling outside the process entirely. Middleware becomes stateless.  
**Resolved decision:**  
**Rationale:**

---

### Q5: Package / project naming
**Status:** OPEN  
**Context:** "SangamMW" is internal. For open source, the name should be search-discoverable, not conflict with existing PyPI packages, and signal purpose.  
**Options:**
- A) `sangam-middleware` / `sangam_mw` — keeps brand alignment; unfamiliar to the open-source community
- B) `universal-connector` — describes function, potentially too generic, likely taken on PyPI
- C) `databridge` — evocative, check PyPI availability
- D) `polyconn` — portmanteau of "polyglot connector", distinctive
- E) Something else entirely  
**Resolved decision:**  
**Rationale:**

---

## Connector Design

### Q6: Class-based connectors vs. dataclass + function dispatch
**Status:** OPEN  
**Context:** v0.1 proposes OOP `BaseConnector` ABC. AgentStudio uses a flat procedural dispatch. There's a genuine tradeoff.  
**Options:**
- A) **ABC classes** — type-safe, IDE-discoverable, natural plugin boundary. Slightly more boilerplate per connector.
- B) **Protocol (structural subtyping)** — duck-typed, no ABC. Lighter. Less enforcement.
- C) **Dataclass config + free functions** — config dataclass carries metadata; functions are `test(config)`, `introspect(config)` etc. Functional style, easy to test.  
**Resolved decision:**  
**Rationale:**

---

### Q7: Async vs. sync connector interface
**Status:** OPEN  
**Context:** FastAPI is async. Most DB drivers exist in both sync and async flavors (psycopg3 has async, motor for MongoDB, etc.). Forcing async everywhere complicates the Python SDK for sync callers.  
**Options:**
- A) **Sync only** — simplest. FastAPI routes use `run_in_executor` to avoid blocking the event loop.
- B) **Async only** — best FastAPI performance. Complicates SDK for synchronous scripts.
- C) **Both via `anyio.from_thread`** — async interface primary, sync wrapper for SDK. Most work.
- D) **Sync core + async thin wrapper** — connectors are sync; FastAPI wraps with `run_in_executor`. Clean for most cases, potential perf ceiling at high concurrency.  
**Resolved decision:**  
**Rationale:**

---

### Q8: How should new connectors be contributed?
**Status:** OPEN  
**Context:** For open source this needs a clear contribution path.  
**Options:**
- A) **In-tree only** — all connectors live in the main `sangam-mw` repo. Simple; one place to look.
- B) **Plugin entry points** — external packages register via `[project.entry-points."sangam_mw.connectors"]`. Allows `pip install sangam-mw-kafka` without touching core. Standard Python plugin pattern.
- C) **Both** — core connectors in-tree; advanced/proprietary connectors as external plugins via entry points.  
**Resolved decision:**  
**Rationale:**

---

## Pipeline Engine

### Q9: Pipeline DAG format — dict vs. Pydantic models vs. graph library
**Status:** OPEN  
**Context:** eInsta uses raw Pydantic models with manual Kahn's sort. Larger pipelines might benefit from networkx.  
**Options:**
- A) **Pydantic models + manual topo sort** (ported from eInsta). No extra deps, proven.
- B) **networkx** — rich graph algorithms, cycle detection, visualization. Adds a dependency.
- C) **Custom DAG class** — thin wrapper over adjacency list; no deps but more code to write.  
**Resolved decision:**  
**Rationale:**

---

### Q10: Transform extensibility — built-in only or plugin transforms?
**Status:** OPEN  
**Context:** eInsta has ~13 built-in transform types. Should users be able to add custom transform nodes (e.g. a Python UDF node, a dbt model node)?  
**Options:**
- A) **Built-in only** for v1.0. Custom transforms are out of scope.
- B) **Plugin transform registry** — same entry-point pattern as connectors. Users can register `MyTransform` implementing `BaseTransform`.
- C) **Python expression node** — one built-in `PythonUDF` node type that accepts a Python lambda/function string. Flexible but has security implications (eval / exec).  
**Resolved decision:**  
**Rationale:**

---

## Operations & Infrastructure

### Q11: Default secrets backend
**Status:** OPEN  
**Context:** Both AgentStudio and eInsta use Fernet key written to `data/.connections_key`. Fine for single-node; not ideal for production.  
**Options:**
- A) **Fernet file store** (current) — simple, works everywhere.
- B) **Fernet file store + Vault (optional)** — default to file, swap to Vault via `SECRETS_BACKEND=vault` env var.
- C) **OS keychain** (macOS Keychain / libsecret on Linux) — natural for desktop tools, not suitable for server deployments.  
**Resolved decision:**  
**Rationale:**

---

### Q12: Observability — logs, metrics, traces
**Status:** OPEN  
**Context:** Neither AgentStudio nor eInsta backend has structured logging or metrics. For open source / production, this matters.  
**Options:**
- A) **structlog** for structured JSON logs + no metrics in v1.0. Add metrics later.
- B) **structlog + prometheus_client** — expose `/metrics` endpoint. Common pattern for FastAPI services.
- C) **OpenTelemetry** — covers logs, metrics, and traces in one SDK. More setup for consumers but most future-proof.  
**Resolved decision:**  
**Rationale:**

---

## Resolved Decisions

*(None yet — this section fills as debates conclude)*

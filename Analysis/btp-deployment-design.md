# SAP BTP Deployment Design
**Date:** 2026-09-21  
**Status:** SUPERSEDED — this document was created based on a misinterpretation. The user clarified that SangamMW is NOT targeting SAP BTP as a deployment platform. BTP was mentioned only as context (BTP uses Node.js and Java) for the runtime language debate. The content below may be useful if BTP deployment becomes a future requirement, but it is not part of the current design.

**Active document for the runtime question:** [runtime-language-decision.md](runtime-language-decision.md)

---

**Context (original, now superseded):** User flagged that SAP BTP supports Node.js and Java natively — this changes the architecture from a single-process Python monolith to a split control plane + execution engine model

---

## The BTP Runtime Reality

SAP BTP has two main compute environments:

| Environment | Runtime support | Best for |
|---|---|---|
| **Cloud Foundry (CF)** | Java, Node.js, Python, Go, .NET — via buildpacks. SAP officially supports Java (Spring Boot + CAP) and Node.js (CAP). Python runs but is not a primary SAP investment. | Apps that consume BTP services (XSUAA, Destination Service, Event Mesh). SAP CAP apps. |
| **Kyma** | Any Docker container — language-agnostic Kubernetes. | Microservices, data-heavy workloads, Python/Go/Rust — anything containerised. |

**Key insight:** We do not have to pick one language for everything. The right approach is to split responsibilities so each layer runs in the environment where it fits best.

---

## Architecture: Control Plane + Execution Engine

### Control Plane — Node.js (CAP) or Java (Spring Boot)
Runs on **BTP Cloud Foundry**. Responsible for everything that touches BTP services and platform operations:

- **Flow management API** — CRUD for flow definitions (create, deploy, version, promote)
- **Scheduling engine** — cron-based trigger management
- **XSUAA authentication** — BTP's OAuth2/JWT auth; Node.js and Java have first-class SAP client libraries
- **SAP Destination Service** — BTP's built-in encrypted credential store → replaces our custom Fernet store on BTP
- **SAP Event Mesh** — publish trigger events, subscribe to queue-based triggers
- **SAP Alert Notification Service** — flow failure/SLA notifications
- **SAP Audit Log Service** — tamper-evident log of all flow executions and config changes
- **BTP Service Manager** — manages service bindings for the execution engine

#### Why Node.js (CAP) specifically for BTP CF?

SAP's Cloud Application Programming Model (CAP) is the recommended way to build applications on BTP. It has first-class support for:
- XSUAA auth wiring (zero-boilerplate)
- OData v4 service exposure (flows become queryable OData entities)
- SAP Destination Service client
- SAP Event Mesh client
- SAP HANA integration

A CAP Node.js app exposing our flow management API is 80% less boilerplate than a raw Express app, because CAP handles all the BTP service wiring.

```javascript
// CAP service definition — Flow Management API
// srv/flow-service.cds
service FlowService @(requires: 'authenticated-user') {
    entity Flows {
        key flow_id    : String;
            name       : String;
            version    : String;
            definition : LargeString;  // YAML content
            status     : String enum { draft; deployed; paused; };
            created_at : Timestamp;
    }
    action deploy(flow_id: String) returns String;
    action run(flow_id: String, payload: LargeString) returns String;
    action promote(flow_id: String, from_env: String, to_env: String) returns String;
}
```

CAP auto-generates OData v4 endpoints, handles XSUAA JWT validation, and provides a SQLite/HANA data layer.

---

### Execution Engine — Python (FastAPI)
Runs on **BTP Kyma** as a Docker container. Responsible for everything that touches data:

- **Flow DAG executor** — parse YAML, topo-sort, execute steps
- **All 73 connectors** — Python drivers for every data source
- **Transform layers** — YAML declarative, DuckDB SQL, Python scripts, PySpark
- **Connection handling** — pools, TTL, token refresh (reads credentials from BTP Destination Service via the control plane)
- **AI/ML** — LLM connectors, vector DB clients, pandas/scikit-learn in transforms

The Python engine exposes a simple internal API that the control plane calls:

```
POST /execute          Run a flow by ID
POST /validate         Validate flow definition
POST /preview          Run with limit, return sample output
GET  /runs/{run_id}    Get execution status + logs
POST /connectors/test  Test a connection config
```

The control plane never touches data. It delegates all execution to the Python engine.

---

## Communication Between Layers

### Option A: REST (HTTP) — simpler, start here
```
CF App (Node.js/Java)  →  Kyma Service (Python)
POST /execute { flow_id, run_id, payload }
→ 202 Accepted { run_id }
GET  /runs/{run_id}
→ 200 { status, rows_processed, steps }
```

The Python engine runs async; the control plane polls or receives a callback when done.

### Option B: gRPC — better for high throughput
```protobuf
service ExecutionEngine {
  rpc Execute(ExecuteRequest) returns (stream ExecuteEvent);
  rpc Validate(FlowDefinition) returns (ValidationResult);
  rpc Preview(ExecuteRequest) returns (PreviewResult);
}
```

gRPC streaming gives real-time progress events (step started, step completed, row counts) back to the control plane — better for the visual designer's live execution view.

### Option C: SAP Event Mesh (async, decoupled)
Control plane publishes `flow.execute.requested` event → Python engine consumes it → publishes `flow.execution.completed`. Fully async, no direct HTTP coupling. Better for long-running flows.

**Recommendation:** Start with REST (Option A). Migrate to Event Mesh (Option C) for production reliability.

---

## BTP Service Mapping

| BTP Service | Role in our middleware | Replaces |
|---|---|---|
| **XSUAA** | OAuth2/JWT auth for all API calls | Our custom JWT auth (backend/auth.py) |
| **Destination Service** | Encrypted storage of connection configs (Salesforce creds, DB passwords) | Our Fernet file store (connections_store.py) |
| **Event Mesh** | Trigger events (flow.execute, flow.complete), async messaging between layers | Our built-in scheduler + Kafka connector |
| **Alert Notification Service** | Flow failure notifications (email, Slack, Teams, PagerDuty) | Our custom error_handler Slack webhook |
| **Audit Log Service** | Immutable execution audit trail | Our structlog execution log |
| **Application Logging** | Centralised log aggregation | Our per-pod logs |
| **BTP Object Store** | Large file staging between steps (Parquet files, etc.) | Local temp files |
| **SAP AI Core** | AI-powered flow suggestions, smart field mapping | Our AI layer (Claude API) — can use either |

### Destination Service Integration (important)

BTP's Destination Service is essentially our Connection Store — it stores encrypted credentials for remote systems. On BTP, instead of our Fernet file store, we bind the Destination Service and read connection configs from it:

```python
# In the Python execution engine on Kyma:
# Read a connection from BTP Destination Service
import requests

def get_connection(dest_name: str) -> dict:
    token = get_xsuaa_token()  # service-to-service OAuth
    resp = requests.get(
        f"{DESTINATION_SVC_URL}/destination-configuration/v1/destinations/{dest_name}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp.json()["destinationConfiguration"]
```

This means connection management in BTP is handled by the platform — no custom Fernet store needed. SAP admins manage connections in the BTP cockpit; our middleware reads them at runtime.

---

## Deployment Topology

### On SAP BTP (full BTP-native)

```
BTP Subaccount
│
├── Cloud Foundry Space
│   └── sangam-mw-control-plane (Node.js CAP app)
│       Bound services: XSUAA, Destination, Event Mesh, Alert Notification, Audit Log
│
└── Kyma Namespace: sangam-mw
    ├── Deployment: sangam-mw-engine (Python FastAPI)
    │   ├── ConfigMap: engine config
    │   ├── Secret: internal API key for control plane → engine auth
    │   └── Service: ClusterIP (internal only)
    ├── Deployment: sangam-mw-spark (PySpark job runner, optional)
    └── Ingress: only control plane is public-facing
```

### On Docker Compose (local dev / non-BTP)

```yaml
# docker-compose.yml
services:
  control-plane:
    image: sangam-mw-control-plane:latest  # Node.js
    ports: ["3000:3000"]
    environment:
      - ENGINE_URL=http://engine:8080
      - SECRETS_BACKEND=fernet    # local Fernet instead of BTP Destination Svc

  engine:
    image: sangam-mw-engine:latest  # Python FastAPI
    ports: ["8080:8080"]
    environment:
      - SECRETS_BACKEND=fernet
```

In local mode, the BTP services are replaced by local equivalents:
- XSUAA → local JWT (same as current AgentStudio auth.py)
- Destination Service → Fernet file store (same as current connections_store.py)
- Event Mesh → local SQLite queue

The codebase supports both via `SECRETS_BACKEND=fernet|destination_service` and `AUTH_BACKEND=local_jwt|xsuaa` env vars.

### On Kubernetes (non-BTP, cloud-agnostic)

```
K8s Cluster (EKS / AKS / GKE)
│
├── sangam-mw-control (Node.js — Deployment + Service)
├── sangam-mw-engine  (Python — Deployment + Service)
├── sangam-mw-postgres (connection store, if not using cloud secret mgr)
└── Ingress → control plane only
```

---

## Decision: Node.js or Java for the Control Plane?

Both work on BTP CF. The choice depends on team preference:

| | Node.js (CAP) | Java (Spring Boot + CAP) |
|---|---|---|
| SAP CAP support | First-class (CDS is JS-native) | First-class (cds4j) |
| BTP service clients | `@sap/xssec`, `@sap/destination-service` | `sap-cloud-sdk-java` (more complete) |
| Code reuse from AgentStudio | High — same TypeScript toolchain | None |
| Team familiarity | High (AgentStudio is TS) | Depends on team |
| SAP enterprise SDK (JCo for RFC/BAPI) | Not available | **Available** |
| Startup time | Fast | Slower (JVM) |
| Memory footprint | Low | Higher |

**Recommendation:** Node.js (CAP) for the control plane, because:
1. AgentStudio is already TypeScript — same team, same toolchain
2. Faster startup in Kyma/CF
3. CAP is CDS-first, and CDS is JavaScript-native
4. If SAP JCo (RFC/BAPI calls) is needed, that goes in a separate Java connector sidecar via our polyglot connector protocol — not in the control plane

---

## What This Changes vs. Original v0.1

| v0.1 assumption | New design |
|---|---|
| Single Python FastAPI monolith | Split: Node.js/CAP control plane + Python execution engine |
| Custom JWT auth | XSUAA on BTP, local JWT for non-BTP (same code, env-switched) |
| Fernet file store for secrets | BTP Destination Service on BTP, Fernet file for non-BTP |
| Custom Slack error notifications | BTP Alert Notification Service on BTP, webhooks elsewhere |
| Python scheduler (APScheduler) | BTP CF task scheduler / Event Mesh on BTP; APScheduler for non-BTP |
| Single deployment target | BTP CF + Kyma, Docker Compose, K8s Helm — same codebase |

The execution engine (Python) does not change. Only the control plane adapts to BTP.

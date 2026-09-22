# Feature Analysis: Enterprise Middleware Comparison
**Date:** 2026-09-21  
**Purpose:** Gap analysis of v0.1 plan vs. Boomi, MuleSoft, SAP CPI, Informatica — and a prioritised feature roadmap to compete  

---

## 1. What the Enterprise Leaders Do

### Boomi (AtomSphere → Boomi Enterprise Platform)
- **Runtime model:** Atoms (single node) / Molecules (HA cluster) — portable, deployable anywhere
- **Transformation:** Visual graphical mapper + Groovy/JS scripting
- **Connectors:** 1,000+ with Marketplace for community connectors
- **Killer features:** DataHub (Golden Records/MDM), Event Streams (Pulsar-based broker), AgentStudio + Agent Control Plane (AI governance), Boomi Data Integration (ELT/CDC, acquired from Rivery)
- **AI:** Boomi Suggest (smart mapping), NL-to-flow generation, AI Gateway for MCP/agent traffic
- **Differentiator:** Largest iPaaS install base; only platform with App Integration + ELT + MDM + AI agent governance in one product

### MuleSoft Anypoint Platform
- **Runtime model:** Mule 4 reactive engine (non-blocking, back-pressure), deployed on CloudHub 2.0 (K8s) or Runtime Fabric (customer K8s)
- **Transformation:** **DataWeave 2.0** — functional transformation language, streaming-capable, handles JSON/XML/CSV/EDI/Parquet/AVRO natively. Best-in-class.
- **Connectors:** 1,200+ certified; Anypoint Exchange as the catalog
- **Killer features:** Anypoint Exchange (reusable asset catalog), API Governance, Agent Fabric (MCP/A2A broker), Flex Gateway (unified API + AI gateway), MUnit (testing framework)
- **AI:** Einstein in Anypoint Code Builder (NL-to-flow + DataWeave generation), Agent Fabric (vendor-neutral AI agent brokering with auth, rate limits, PII filtering)
- **Differentiator:** DataWeave; strongest API management; Agent Fabric as neutral AI governance layer

### SAP Integration Suite (Cloud Platform Integration)
- **Runtime model:** Apache Camel-based iFlows on SAP BTP (Cloud Foundry), with Edge Integration Cell (customer-managed K8s on-prem runtime)
- **Transformation:** Graphical mapper + XSLT + Groovy/JS + Integration Advisor (ML-assisted B2B mapping)
- **Connectors:** 70+ native + 150 Open Connectors + 2,000+ pre-packaged iFlow templates for SAP scenarios
- **Killer features:** Integration Advisor (ML for EDIFACT/X12 mapping), Edge Integration Cell (data residency), Advanced Event Mesh (Solace-based, enterprise event fabric), Trading Partner Management
- **AI:** Joule NL-to-iFlow (2026), Integration Advisor ML, MCP tool exposure
- **Differentiator:** Unmatched SAP ecosystem depth; best hybrid story for strict data-residency needs; Advanced Event Mesh

### Informatica IDMC
- **Runtime model:** Secure Agent (lightweight on-prem data plane) + IDMC cloud control plane; Cloud Data Integration (CDI) + Cloud Application Integration (CAI)
- **Transformation:** Visual mapper + SQL + Python/Spark + ELT push-down (Snowflake, Databricks, BigQuery native)
- **Connectors:** 300+ data sources; GenAI connectors (NVIDIA NIM, Databricks AI, Snowflake Cortex)
- **Killer features:** Cloud Data Quality (500+ rules, CLAIRE DQ Agent), Multidomain MDM (golden records + stewardship), Data Catalog (column-level lineage, PII detection, business glossary), ELT push-down
- **AI:** CLAIRE Agents (DQ, ELT, Exploration, MDM), CLAIRE GPT (NL queries on data), MCP server exposure, Amazon Bedrock AgentCore integration
- **Differentiator:** Best-in-market Data Quality + MDM + Catalog combination; most advanced AI for data management

---

## 2. Gap Analysis: v0.1 vs. Enterprise Leaders

### What v0.1 Already Has ✓
| Feature | v0.1 State | Quality Gap |
|---|---|---|
| 26-connector registry | ✓ Draft architecture | Medium — class-based design not yet built |
| Auth framework | ✓ Designed | Small — well-documented patterns |
| Connection pooling | ✓ TTL-based | Medium — won't survive multi-worker |
| PySpark + Pandas pipeline engine | ✓ Ported from eInsta | Small — subprocess isolation proven |
| DAG / topological sort | ✓ Ported from eInsta | Small |
| FastAPI REST surface | ✓ Designed | Small |
| Fernet secrets store | ✓ Designed | Medium — file-only, no Vault |

### Critical Gaps (blocks enterprise competitiveness)
| # | Feature | Why Critical | Best Reference |
|---|---|---|---|
| G1 | **Visual / Low-Code Integration Designer** | Without a canvas, only developers can use it. Rules out IT ops, citizen integrators. | Boomi AtomSphere |
| G2 | **Data Transformation Language** | Every integration transforms data. Procedural Python code is too verbose for business logic. Need a mapping tool or DSL. | MuleSoft DataWeave |
| G3 | **Message Processing Patterns** | No router, splitter, scatter-gather, aggregator, until-successful, or batch scope in v0.1. Can't build complex orchestrations. | MuleSoft Batch scope + Choice Router |
| G4 | **Event-Driven Architecture / Streaming** | Real-time use cases (CDC, IoT, fraud) need event bus + Kafka. Polling-only middleware can't compete. | Boomi Event Streams; SAP Advanced Event Mesh |
| G5 | **API Management** | Publish, secure, version, throttle, and monitor APIs. Without this, the platform can consume APIs but not manage them. | MuleSoft Anypoint API Manager + Flex Gateway |
| G6 | **Observability + OpenTelemetry** | Production requires real-time dashboards, distributed tracing, alerting, and log search. | Boomi OpenTelemetry (GA 2025) |
| G7 | **B2B / EDI** | Supply chain, healthcare, retail — all require X12, EDIFACT, AS2 out of the box. | SAP Integration Advisor; Boomi B2B Management |
| G8 | **Reusable Asset Catalog / Integration Marketplace** | Teams duplicate work without a searchable catalog of connectors, flows, and templates. | MuleSoft Anypoint Exchange |
| G9 | **CI/CD + Git-native deployment** | DevOps teams won't adopt without pipeline automation and version-controlled artifacts. | MuleSoft Anypoint CLI + MUnit |
| G10 | **AI-Assisted Flow Development** | NL-to-flow, smart field mapping, and AI-assisted debugging reduce build time 40–60%. Competitors shipped this in 2024–2025. | MuleSoft Einstein + Agent Fabric |

### Important Gaps (needed for growth, not day-1)
| # | Feature | Why Important |
|---|---|---|
| G11 | **AI Agent Governance / MCP Control Plane** | The fastest-growing enterprise AI concern in 2026 is agent sprawl. Platform that governs MCP/A2A traffic becomes the control plane for AI infrastructure. |
| G12 | **Hybrid / On-Prem Runtime** | Regulated industries (banking, healthcare, government) require data residency. Cloud-only is disqualified from enterprise deals. |
| G13 | **Compliance Certifications** | SOC 2, HIPAA, FedRAMP gate government and healthcare procurement. |
| G14 | **Managed File Transfer (MFT)** | High-volume batch file movement (payroll, bank statements) still dominant in B2B. |
| G15 | **Master Data Management** | Golden records across integrated systems prevent data inconsistency at scale. |
| G16 | **Data Quality + Profiling** | AI and compliance both need demonstrably clean data. DQ rules + profiling eliminate the need for a separate tool. |
| G17 | **Integration Content Catalog (pre-built flows)** | Time-to-value wins POC evaluations. SAP has 2,000+ pre-packaged iFlows; we start with 0. |
| G18 | **ELT / CDC Pipeline** | Data engineering teams need CDC (log-based change capture) and ELT push-down to warehouses. Merges app integration + data integration stories. |

---

## 3. Full Feature Roadmap (Phased)

### Tier 0 — Foundation (v0.1, current plan)
*Build the solid engine nobody sees but everyone depends on*

- [x] **Connector Plugin Registry** — class-based, entry-point extensible, 30+ connectors
- [x] **Auth Framework** — Bearer, Basic, ApiKey, OAuth2CC, ServiceAccount, JWT Bearer, AWS SigV4
- [x] **Connection Manager** — TTL pooling, health check, Fernet encryption, named connection store
- [x] **Schema Introspection API** — tables, columns, sample rows across all connector types
- [x] **Pipeline Engine** — DAG model, PySpark + Pandas engines, subprocess isolation, file sources/sinks
- [x] **REST API** — connector test, introspect, sample, pipeline validate/preview/run
- [x] **Python SDK** — thin client for programmatic use
- [x] **Basic JWT auth** for the API itself

---

### Tier 1 — Developer Platform (v0.2, highest priority gaps)
*Make it usable as a real integration tool, not just a connector library*

#### T1.1 — Data Transformation Engine
**Gap addressed: G2**

A Python-native transformation DSL. Not DataWeave (too Java-centric) but inspired by it:
- **Transformation pipeline** — chain of steps: `map`, `filter`, `enrich`, `aggregate`, `convert`
- **Expression evaluator** — JSONPath, XPath, Jinja2 templates for field mapping
- **Format conversion** — JSON ↔ XML ↔ CSV ↔ Parquet ↔ Avro ↔ YAML (built on existing pandas/PySpark)
- **Field mapping spec** — declarative YAML/JSON mapping definition (source field → target field, with transformations)
- **Script step** — inline Python lambda/function for custom logic; sandboxed exec

```yaml
# Example mapping spec
mapping:
  source_format: json
  target_format: xml
  fields:
    - source: $.customer.id
      target: /Order/CustomerId
      transform: uppercase
    - source: $.order.total
      target: /Order/Amount
      transform: round(2)
```

#### T1.2 — Message Processing Patterns
**Gap addressed: G3**

Flow-level orchestration shapes (beyond simple source → transform → sink):
- **Router** — content-based, header-based conditional routing to branches
- **Splitter** — iterate over arrays; fan-out to parallel sub-pipelines
- **Aggregator** — collect results from split branches and merge
- **Scatter-Gather** — fan-out to multiple connectors in parallel, aggregate all responses
- **Until-Successful** — retry with exponential backoff (configurable max retries, delay)
- **Try-Catch** — error handling scope with configurable dead-letter behavior
- **Circuit Breaker** — auto-trip on consecutive connector failures, with recovery probe
- **Async Step** — fire-and-forget branch, returns immediately

#### T1.3 — Trigger System
**Gap addressed: G4 (partial)**

How flows start:
- **HTTP Trigger** — webhook / REST endpoint trigger; integration becomes an API endpoint
- **Scheduler** — cron expression-based triggers (replace the "run manually" only model)
- **File Watcher** — poll SFTP/S3/Azure Blob/local path for new files
- **Database Trigger** — poll a table for new/changed rows (watermark-based)
- **Message Queue Trigger** — consume from Kafka, RabbitMQ, SQS, Azure Service Bus
- **Webhook** — inbound webhook with signature validation (GitHub, Stripe, Slack style)

#### T1.4 — Flow Model (replacing "Pipeline")
**Gap addressed: G3, connects T1.2 + T1.3**

Promote the core execution unit from "Pipeline" to "Flow":

```
Flow = {
  trigger: TriggerConfig,           # how it starts
  steps: list[Step],                # ordered graph of steps
  error_handler: ErrorHandlerConfig,
  environment: str,                 # dev | staging | prod
  version: str,
}

Step = ConnectorStep | TransformStep | RouterStep | ScriptStep | FlowCallStep
```

A Flow is versioned, storable in Git, and deployable across environments (dev/staging/prod) — the same model as Boomi packaged components.

#### T1.5 — Monitoring + Observability
**Gap addressed: G6**

- **Structured logging** — `structlog` with JSON output; every flow execution emits a structured trace
- **Execution history** — per-flow execution log: trigger time, step durations, row counts, status
- **OpenTelemetry export** — traces, metrics, and logs exportable to Datadog, Grafana, Honeycomb, Jaeger
- **`/metrics` endpoint** — Prometheus-compatible metrics: flow execution count, latency histogram, error rate
- **Alerting webhooks** — POST to webhook on flow failure, SLA breach, or connector error
- **Dashboard** — lightweight built-in dashboard (optional; can be replaced by Grafana)

#### T1.6 — CI/CD + Developer Experience
**Gap addressed: G9**

- **CLI** (`sangam-mw`) — `flow deploy`, `flow run`, `flow logs`, `connector test`, `env create`
- **Flow-as-code** — flows defined in YAML/JSON, stored in Git, versioned
- **Environment promotion** — `sangam-mw flow promote --from dev --to prod`
- **Testing framework** — `sangam-mw flow test` with mock connectors, assertion library
- **GitHub Actions integration** — official `sangam-mw/deploy-flow` action
- **Docker Compose** — local dev stack with all dependencies in one `docker-compose.yml`

---

### Tier 2 — Integration Platform (v0.3, growth features)
*Expand the audience from developers to platform engineers and enterprise architects*

#### T2.1 — API Management Gateway
**Gap addressed: G5**

A lightweight API gateway wrapping the Flow HTTP triggers:
- **API proxy** — expose a Flow as a managed API with a stable versioned URL (`/api/v1/orders`)
- **Rate limiting** — per-consumer, per-plan quotas (100 req/min, 10,000 req/day)
- **Auth policies** — OAuth2 PKCE, JWT validation, API key, mTLS at the gateway
- **API versioning** — route `/api/v1/` and `/api/v2/` to different Flow versions simultaneously
- **Developer portal** — auto-generated from OpenAPI spec; self-service API key provisioning
- **API analytics** — request volume, latency p50/p95/p99, error rate per endpoint
- **Policy plugins** — CORS, IP allowlist, request transformation, response caching

#### T2.2 — Event Streaming (Built-in Broker)
**Gap addressed: G4 (full)**

- **Built-in message broker** — lightweight, embeddable broker for pub/sub (options: Redpanda embedded, NATS JetStream, or Kafka-compatible API wrapper)
- **Topic management** — create, delete, configure retention, partitions
- **Consumer groups** — competing consumer and fan-out patterns
- **Dead letter topics** — automatic DLQ on processing failure with configurable retry
- **Kafka bridge** — bidirectional bridge to external Kafka clusters
- **Cloud queue connectors** — SQS, Azure Service Bus, Google Pub/Sub, RabbitMQ as first-class trigger sources

#### T2.3 — B2B / EDI Module
**Gap addressed: G7**

- **EDI parser** — X12, EDIFACT, HL7 v2 parsing and validation (using `pyx12` / `python-edifact` / `hl7apy`)
- **EDI generator** — X12, EDIFACT document generation from internal data models
- **Trading Partner Registry** — per-partner: interchange IDs, protocol config, agreement record
- **Protocol support** — AS2 (Mendelson-compatible), SFTP, HTTPS, FTP
- **Acknowledgment management** — auto-generate 997 (X12), CONTRL (EDIFACT) on receive
- **B2B Monitoring** — dedicated dashboard for EDI transaction status by partner

#### T2.4 — Reusable Asset Catalog
**Gap addressed: G8**

- **Flow templates** — curated library of tested, documented integration templates (e.g. "Salesforce → PostgreSQL sync", "Shopify order → SAP iDoc", "S3 → BigQuery")
- **Connector metadata catalog** — searchable registry of all installed connectors with docs, auth requirements, known limitations
- **Community marketplace** — submit, discover, and install community-contributed connectors and flow templates via `pip install sangam-mw-[name]` + registry entry
- **Version tracking** — each template has a semver; teams pin to a version

#### T2.5 — Hybrid Runtime
**Gap addressed: G12**

- **Runtime Agent** — lightweight, self-contained Python process (like Boomi's Atom) that can run anywhere: cloud VM, on-prem server, Docker, K8s pod
- **Control Plane / Data Plane separation** — flows are designed and monitored in the central SangamMW server; executed by a Runtime Agent that can be on-prem
- **No inbound port required** — Agent polls control plane over outbound HTTPS (same model as Informatica Secure Agent)
- **Multi-environment** — one control plane, many agents (dev, staging, prod, region-A, region-B)

#### T2.6 — AI-Assisted Development
**Gap addressed: G10**

- **NL-to-Flow generation** — describe the integration in English; Claude generates the Flow YAML
- **Smart field mapping** — given source and target schemas, AI suggests field mappings with confidence scores
- **Flow debugger copilot** — explain a failed execution, suggest fix
- **Connector recommendation** — given a description ("I need to read customer data from Salesforce and write to PostgreSQL"), recommend the right connectors and a starter template
- **Anomaly detection** — flag unusual execution patterns (sudden latency spike, row count drop) with AI explanation

---

### Tier 3 — Enterprise Platform (v1.0+, differentiation features)
*The features that win enterprise deals and RFPs*

#### T3.1 — AI Agent Governance (MCP Control Plane)
**Gap addressed: G11**

This is the highest-growth feature area in 2026 — every major iPaaS vendor is rushing to ship it:
- **MCP Server Registry** — register, version, and discover all MCP tools/servers in the enterprise
- **Agent Registry** — catalog of all AI agents (Claude, GPT, Gemini, Bedrock, Vertex AI) connected to the platform
- **AI Gateway** — single policy enforcement point for all LLM/MCP calls:
  - Auth (every agent call authenticated)
  - Rate limiting per agent / per model
  - PII detection + masking before prompts leave the enterprise
  - Prompt injection detection
  - Cost tracking (tokens per agent, per use case)
  - Audit trail (who called what LLM with what prompt)
- **A2A Broker** — route Agent-to-Agent calls through the gateway (same policy enforcement as API calls)
- **Expose SangamMW flows as MCP tools** — every flow becomes a callable tool for any AI agent

#### T3.2 — Master Data Management (Golden Records)
**Gap addressed: G15**

- **Entity Hub** — define master entity types (Customer, Product, Supplier, etc.) with field definitions and survivorship rules
- **Golden Record engine** — ingest records from multiple source systems, match (exact + fuzzy), merge per survivorship rules
- **Stewardship UI** — human-in-the-loop review for low-confidence matches
- **Source tracking** — which source system "owns" each field; audit trail of all changes
- **MDM as connector** — downstream systems subscribe to golden records via the standard connector interface

#### T3.3 — Data Quality + Profiling
**Gap addressed: G16**

- **Data Profiler** — run on any connector source: null%, distinct%, min/max/mean, value distribution, pattern detection (email, phone, date)
- **Rule Engine** — define DQ rules (not-null, regex match, range check, referential integrity, cross-field) applied as a pipeline step
- **DQ Scorecard** — track data quality score over time per source per entity
- **AI rule suggestion** — describe data quality requirements in English; AI generates rules
- **Bad-record quarantine** — configurable: reject, flag, or route bad records to a DLQ

#### T3.4 — ELT / CDC Pipeline
**Gap addressed: G18**

- **Log-based CDC** — PostgreSQL pgoutput/wal2json, MySQL binlog, Oracle LogMiner, SQL Server CDC (via Debezium under the hood)
- **ELT push-down** — for Snowflake, BigQuery, Databricks: generate and execute native SQL/SQL instead of pulling data through the SangamMW process
- **Incremental load strategies** — high-watermark, full refresh, merge (upsert), append
- **Stream-to-lake** — continuous micro-batch or streaming ingest to Delta Lake, Iceberg, Hudi targets

#### T3.5 — Compliance + Security Hardening
**Gap addressed: G13**

- **Audit log** — immutable, tamper-evident log of every flow execution, config change, and user action
- **Field-level encryption** — encrypt specific fields in transit within flows (PII, PCI data)
- **Data masking** — mask/tokenize sensitive fields for non-prod environments
- **SOC 2 Type II** documentation and controls
- **RBAC with fine-grained permissions** — per-environment, per-flow, per-connector ACLs
- **mTLS** — mutual TLS for connector connections and Runtime Agent ↔ Control Plane communication

---

## 4. Our Differentiation Strategy

The enterprise iPaaS market is dominated by Java-based, GUI-first, proprietary platforms with 10–20 year head starts. We cannot win by replicating them feature-for-feature. We win by being:

### Differentiator 1: Python-Native + Data-Engineer-Friendly
- DataWeave is powerful but Java-ecosystem-only; data engineers don't know it
- Pandas, PySpark, and Python lambdas are the lingua franca of every data team
- Our transformation engine is Python-first; data engineers can write flows that feel like notebooks

### Differentiator 2: AI-Native, Not AI-Bolted-On
- Competitors added AI in 2024–2025 as a layer on top of 15-year-old architectures
- We design the AI layer into the core: NL-to-flow, MCP tool exposure, agent governance from v0.2
- Every flow is callable as an MCP tool automatically — no extra configuration

### Differentiator 3: Truly Open Source (Not Open Core)
- Boomi, MuleSoft, SAP, Informatica are all proprietary — no community can extend them freely
- Our entire platform is Apache 2.0; all 26+ connectors in the same repo
- Community connectors via `pip install sangam-mw-kafka` — zero fork required
- This is the "Linux of middleware" opportunity; enterprise support contract on top

### Differentiator 4: Git-Native, DevOps-First
- Flows are YAML files stored in Git — just like K8s manifests or dbt models
- `sangam-mw flow deploy` from CI/CD; no point-and-click required
- Immutable versioned deployments; rollback is `git revert`
- This is what MuleSoft is rushing toward with Anypoint Code Builder; we start there

### Differentiator 5: Connector Marketplace as Package Registry
- Publishing a connector is `pip install sangam-mw-[name]` + PyPI
- Boomi/MuleSoft connectors require vendor certification and platform-specific toolchains
- Our model: any Python developer can ship a connector; community vets it via PyPI downloads + GitHub stars

---

## 5. Feature Priority Matrix

| Feature | Enterprise Impact | Build Effort | Priority |
|---|---|---|---|
| Data Transformation DSL (T1.1) | ★★★★★ | Medium | **P0** |
| Message Routing Patterns (T1.2) | ★★★★★ | Medium | **P0** |
| Trigger System (T1.3) | ★★★★★ | Medium | **P0** |
| Observability + OpenTelemetry (T1.5) | ★★★★☆ | Low | **P0** |
| CI/CD + CLI (T1.6) | ★★★★☆ | Low | **P0** |
| API Management Gateway (T2.1) | ★★★★★ | High | **P1** |
| Event Streaming / Built-in Broker (T2.2) | ★★★★★ | High | **P1** |
| AI-Assisted Development (T2.6) | ★★★★★ | Medium | **P1** |
| B2B / EDI (T2.3) | ★★★★☆ | High | **P1** |
| Asset Catalog + Templates (T2.4) | ★★★☆☆ | Low | **P1** |
| Hybrid Runtime Agent (T2.5) | ★★★★☆ | Medium | **P1** |
| AI Agent Governance / MCP (T3.1) | ★★★★★ | High | **P2** |
| ELT / CDC (T3.4) | ★★★★☆ | High | **P2** |
| Data Quality + Profiling (T3.3) | ★★★★☆ | High | **P2** |
| Master Data Management (T3.2) | ★★★☆☆ | Very High | **P3** |
| Compliance / SOC 2 hardening (T3.5) | ★★★☆☆ | Medium | **P2** |

---

## 6. Revised Architecture (post-enterprise feature expansion)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          SangamMW Platform                                    │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  Interface Layer                                                      │    │
│  │  REST API  ·  gRPC  ·  CLI (sangam-mw)  ·  Python SDK  ·  UI Canvas │    │
│  └───────────────────────────────┬──────────────────────────────────────┘    │
│                                  │                                            │
│  ┌───────────────┐  ┌────────────▼──────────┐  ┌──────────────────────────┐ │
│  │  API Gateway  │  │  Flow Execution Engine│  │  AI Layer                │ │
│  │  - Auth       │  │  - DAG orchestration  │  │  - NL-to-Flow            │ │
│  │  - Rate limit │  │  - Router/Splitter    │  │  - Smart field mapping   │ │
│  │  - Policies   │  │  - Retry/Circuit BKR  │  │  - AI Agent Governance   │ │
│  │  - Developer  │  │  - Scatter-Gather     │  │  - MCP Control Plane     │ │
│  │    Portal     │  │  - Batch              │  │  - PII masking           │ │
│  └───────────────┘  └───────────────────────┘  └──────────────────────────┘ │
│                                  │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │  Trigger System                                                          │ │
│  │  HTTP Webhook  ·  Scheduler (cron)  ·  File Watcher  ·  DB Watermark   │ │
│  │  Message Queue (Kafka/SQS/AMQP)  ·  CDC (log-based)  ·  Event Mesh    │ │
│  └──────────────────────────────────────────────────────────────────────── ┘ │
│                                  │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │  Data Layer                                                              │ │
│  │  ┌─────────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────┐ │ │
│  │  │ Transformation  │  │ Data Quality │  │     MDM    │  │    ELT    │ │ │
│  │  │ Engine          │  │ + Profiler   │  │  (Golden   │  │  + CDC    │ │ │
│  │  │ (DSL + Scripts) │  │              │  │  Records)  │  │           │ │ │
│  │  └─────────────────┘  └──────────────┘  └────────────┘  └───────────┘ │ │
│  └──────────────────────────────────────────────────────────────────────── ┘ │
│                                  │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │  Connector Registry (Plugin System — entry-point extensible)            │ │
│  │  SQL · NoSQL · REST · Storage · Graph · Cache · Analytics · SaaS · B2B │ │
│  └──────────────────────────────────────────────────────────────────────── ┘ │
│                                  │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │  Infrastructure                                                          │ │
│  │  Connection Pool  ·  Secrets (Fernet + Vault)  ·  RBAC  ·  Audit Log   │ │
│  │  OpenTelemetry  ·  Prometheus  ·  Structured Logging (structlog)        │ │
│  └──────────────────────────────────────────────────────────────────────── ┘ │
│                                  │                                            │
│  ┌──────────────────────────────▼──────────────────────────────────────────┐ │
│  │  Runtime Deployment Options                                              │ │
│  │  Docker Compose  ·  K8s Helm Chart  ·  Runtime Agent (on-prem)         │ │
│  │  CloudHub-style managed (future)                                        │ │
│  └──────────────────────────────────────────────────────────────────────── ┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Competitive Positioning Statement

> **SangamMW is the open-source, Python-native, AI-first middleware platform for teams who want enterprise integration power without enterprise vendor lock-in.**
>
> We match Boomi's connector breadth, MuleSoft's API management depth, SAP's hybrid deployment model, and Informatica's data quality foundation — in a single open-source project that deploys in 5 minutes and is extended with a `pip install`.

**Target buyers (Year 1):**
- Data engineering teams who hate Java-based iPaaS
- Platform engineering teams building internal integration infrastructure
- AI teams who need reliable, governed data pipelines feeding LLM applications
- Mid-market companies priced out of Boomi/MuleSoft ($150K+ ACV)

---

## 8. What This Means for v0.2

The v0.2 plan should focus exclusively on **Tier 1 features** (T1.1–T1.6):

1. **Transformation Engine** — declarative mapping spec + Python script step
2. **Message Processing Shapes** — Router, Splitter, Aggregator, Until-Successful, Try-Catch
3. **Trigger System** — HTTP, Scheduler, File Watcher, Message Queue
4. **Flow Model** — replace "Pipeline" concept with versioned, Git-storable "Flow"
5. **Observability** — structlog, OpenTelemetry export, execution history, /metrics
6. **CLI** — `sangam-mw` with flow deploy/run/test/logs commands

These 6 features transform the v0.1 connector library into an actual integration platform.

See [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) — questions Q1–Q12 still need resolution before locking v0.2.

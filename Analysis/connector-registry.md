# SangamMW — Connector Registry
**Last updated:** 2026-09-21  
**Total connectors:** 50  
**Source:** AgentStudio (26 existing) + gaps identified in enterprise comparison

---

## Priority Key

| Label | Meaning |
|---|---|
| `[AS]` | Already in AgentStudio — port directly |
| `[P0]` | Must-add — critical gap, blocks middleware credibility |
| `[P1]` | Should-add — important for growth / enterprise coverage |
| `[P2]` | Nice-to-have — rounds out coverage, lower urgency |

---

## Family 1 — SQL / OLTP (Transactional)

| Connector ID | Label | Driver | Priority |
|---|---|---|---|
| `postgres` | PostgreSQL | psycopg3 | `[AS]` |
| `mysql` | MySQL | pymysql | `[AS]` |
| `mssql` | SQL Server | pymssql | `[AS]` |
| `oracle` | Oracle | oracledb | `[AS]` |
| `hana` | SAP HANA | hdbcli | `[AS]` |
| `azure-sql` | Azure SQL Database | pymssql | `[AS]` |
| `sqlite` | SQLite | stdlib sqlite3 | `[AS]` |
| `mariadb` | MariaDB | pymysql (dialect) | `[P2]` |
| `cockroachdb` | CockroachDB | psycopg3 (dialect) | `[P2]` |

---

## Family 2 — Analytics / OLAP / Data Warehouse

| Connector ID | Label | Driver | Priority |
|---|---|---|---|
| `snowflake` | Snowflake | snowflake-connector-python | `[AS]` |
| `databricks` | Databricks SQL | databricks-sql-connector | `[AS]` |
| `redshift` | Amazon Redshift | psycopg3 (sslmode=require) | `[AS]` |
| `bigquery` | Google BigQuery | google-cloud-bigquery | `[AS]` |
| `clickhouse` | ClickHouse | clickhouse-driver | `[P1]` |
| `duckdb` | DuckDB | duckdb (in-process) | `[P1]` |

---

## Family 3 — NoSQL / Document / Search

| Connector ID | Label | Driver | Priority |
|---|---|---|---|
| `mongodb` | MongoDB | pymongo | `[AS]` |
| `elasticsearch` | Elasticsearch / OpenSearch | elasticsearch-py | `[P0]` |
| `dynamodb` | AWS DynamoDB | boto3 | `[P0]` |
| `cosmos-db` | Azure Cosmos DB | azure-cosmos | `[P1]` |
| `cassandra` | Apache Cassandra | cassandra-driver | `[P1]` |
| `firestore` | Google Firestore | google-cloud-firestore | `[P2]` |
| `couchbase` | Couchbase | couchbase | `[P2]` |

---

## Family 4 — Messaging / Streaming  
*Biggest gap in the current AgentStudio set — zero coverage today*

| Connector ID | Label | Driver | Priority |
|---|---|---|---|
| `kafka` | Apache Kafka | confluent-kafka-python | `[P0]` |
| `sqs` | Amazon SQS / SNS | boto3 | `[P0]` |
| `azure-service-bus` | Azure Service Bus | azure-servicebus | `[P0]` |
| `google-pubsub` | Google Cloud Pub/Sub | google-cloud-pubsub | `[P1]` |
| `rabbitmq` | RabbitMQ | pika | `[P1]` |
| `azure-event-hubs` | Azure Event Hubs | azure-eventhub | `[P1]` |
| `nats` | NATS / JetStream | nats-py | `[P2]` |

---

## Family 5 — Cloud Storage / Object Storage / Files

| Connector ID | Label | Driver | Priority |
|---|---|---|---|
| `aws-s3` | Amazon S3 | boto3 | `[AS]` |
| `azure-blob` | Azure Blob Storage | azure-storage-blob | `[AS]` |
| `google-drive` | Google Drive / Sheets | google-api-python-client | `[AS]` |
| `onedrive` | Microsoft OneDrive | msgraph-sdk | `[AS]` |
| `sharepoint` | SharePoint | msgraph-sdk | `[AS]` |
| `ftp-sftp` | FTP / SFTP | paramiko / ftplib | `[AS]` |
| `gcs` | Google Cloud Storage | google-cloud-storage | `[P0]` |
| `minio` | MinIO (S3-compatible) | boto3 (endpoint override) | `[P1]` |
| `dropbox` | Dropbox | dropbox | `[P2]` |
| `box` | Box | boxsdk | `[P2]` |

---

## Family 6 — Graph

| Connector ID | Label | Driver | Priority |
|---|---|---|---|
| `neo4j` | Neo4j | neo4j (official driver) | `[AS]` |

---

## Family 7 — Cache

| Connector ID | Label | Driver | Priority |
|---|---|---|---|
| `redis` | Redis | redis-py | `[AS]` |

---

## Family 8 — REST / Generic API

| Connector ID | Label | Auth Types | Priority |
|---|---|---|---|
| `rest` | Generic REST API | none, bearer, basic, apiKeyHeader, apiKeyQuery, customHeaders, oauth2CC | `[AS]` |
| `salesforce` | Salesforce | salesforceClientCredentials, salesforceJwtBearer | `[AS]` |

---

## Family 9 — AI / Vector  
*Zero coverage today — table stakes for an AI-native middleware in 2026*

| Connector ID | Label | Driver / API | Priority |
|---|---|---|---|
| `pinecone` | Pinecone | pinecone-client | `[P0]` |
| `weaviate` | Weaviate | weaviate-client | `[P0]` |
| `qdrant` | Qdrant | qdrant-client | `[P0]` |
| `openai` | OpenAI / Azure OpenAI | openai | `[P1]` |
| `anthropic` | Anthropic Claude API | anthropic | `[P1]` |
| `aws-bedrock` | AWS Bedrock | boto3 (bedrock-runtime) | `[P1]` |
| `vertex-ai` | Google Vertex AI | google-cloud-aiplatform | `[P2]` |
| `chroma` | Chroma | chromadb | `[P2]` |
| `pgvector` | pgvector (PostgreSQL ext.) | psycopg3 + pgvector | `[P2]` |

---

## Family 10 — SaaS / Communication

| Connector ID | Label | Auth | Priority |
|---|---|---|---|
| `slack` | Slack | Bot Token (Bearer) | `[AS]` |
| `github` | GitHub | PAT / Bearer | `[AS]` |
| `jira` | Jira Cloud | Basic (email + API token) | `[AS]` |
| `hubspot` | HubSpot CRM | Bearer (Private App) | `[AS]` |
| `teams` | Microsoft Teams | OAuth2 CC (Graph API) | `[P0]` |
| `stripe` | Stripe | Bearer (Secret Key) | `[P0]` |
| `sendgrid` | SendGrid | Bearer | `[P0]` |
| `mailgun` | Mailgun | Basic Auth | `[P0]` |
| `twilio` | Twilio | Basic (AccountSID + AuthToken) | `[P0]` |
| `servicenow` | ServiceNow | Basic / OAuth2 | `[P1]` |
| `shopify` | Shopify | Bearer (Admin API Token) | `[P1]` |
| `workday` | Workday | OAuth2 CC | `[P1]` |
| `zendesk` | Zendesk | Basic / Bearer | `[P1]` |
| `notion` | Notion | Bearer (Integration Token) | `[P1]` |
| `airtable` | Airtable | Bearer | `[P2]` |
| `freshdesk` | Freshdesk | Basic | `[P2]` |
| `monday` | Monday.com | Bearer | `[P2]` |
| `intercom` | Intercom | Bearer | `[P2]` |
| `mailchimp` | Mailchimp | Basic / OAuth2 | `[P2]` |
| `marketo` | Marketo | OAuth2 CC | `[P2]` |
| `ms-dynamics` | Microsoft Dynamics 365 | OAuth2 (MSAL) | `[P2]` |
| `netsuite` | Oracle NetSuite | OAuth2 / Token-Based | `[P2]` |

---

## Summary by Priority

| Priority | Count | Description |
|---|---|---|
| `[AS]` existing | 26 | Port from AgentStudio |
| `[P0]` must-add | 13 | Kafka, SQS, Azure SB, GCS, Elasticsearch, DynamoDB, Teams, Stripe, SendGrid, Mailgun, Twilio, Pinecone, Weaviate, Qdrant |
| `[P1]` should-add | 16 | ClickHouse, DuckDB, Cosmos DB, Cassandra, Pub/Sub, RabbitMQ, Event Hubs, MinIO, OpenAI, Anthropic, Bedrock, ServiceNow, Shopify, Workday, Zendesk, Notion |
| `[P2]` nice-to-have | 18 | Firestore, Couchbase, NATS, Dropbox, Box, Vertex AI, Chroma, pgvector, MariaDB, CockroachDB, Airtable, Freshdesk, Monday.com, Intercom, Mailchimp, Marketo, Dynamics 365, NetSuite |
| **Total** | **73** | |

---

## Implementation Notes

### Connectors with shared driver base
- `mariadb` → same as `mysql` (pymysql), just different dialect defaults
- `cockroachdb` → same as `postgres` (psycopg3), different SQL dialect
- `azure-sql` → same as `mssql` (pymssql)
- `minio` → same as `aws-s3` (boto3) with custom `endpoint_url`
- `pgvector` → extends `postgres` connector with vector search methods
- `mailgun` → can share same base as `sendgrid` (HTTP REST connector)

### Kafka connector specifics
Use `confluent-kafka-python` (not `kafka-python` — it is unmaintained). Support:
- Produce: single message, batch, with schema registry (Avro/JSON Schema)
- Consume: consumer group, offset management, seek
- Auth: PLAINTEXT, SASL_PLAINTEXT, SASL_SSL (SCRAM-SHA-256, OAUTHBEARER)
- Confluent Cloud, MSK, Azure Event Hubs (Kafka endpoint), Redpanda all supported

### AI / LLM connector pattern
LLM connectors differ from data connectors — they don't have `introspect_objects` / `introspect_columns`. They expose:
- `complete(prompt, model, params) → str`
- `embed(texts, model) → list[list[float]]`
- `list_models() → list[str]`

Vector DB connectors expose:
- `upsert(vectors, metadata)`
- `query(vector, top_k, filters) → list[Match]`
- `delete(ids)`
- `list_collections() → list[str]`

These two new connector types need thin subclasses of `BaseConnector` with their own abstract method sets — they don't fit the `introspect_objects` pattern.

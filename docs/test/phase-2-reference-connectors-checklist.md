# Phase 2 — Reference connectors validation

**Date:** 2026-09-21  
**Plan:** `mw-plan.md` Phase 2 (file already in Phase 1; plus Salesforce, S3, Postgres, REST)

## How to run

```bash
./docs/test/run-phase-2-validation.sh
```

## Expected evidence

Implementations follow AgentStudio (`/Users/vijayreddy/github/AgentStudio`) runtime:

- Salesforce: `db_salesforce.py.eta` + `salesforce_security.py` (client credentials / JWT bearer, instance_url from token, safe `nextRecordsUrl`)
- REST: `db_rest.py.eta` auth types (`none`, `bearer`, `apiKeyHeader`, `apiKeyQuery`, `basic`, `customHeaders`, `oauth2ClientCredentials`)
- S3: `awsS3Connector.ts` (IAM fallback, session token)
- Postgres: `SQL_DIALECTS.postgres` (`postgresql+psycopg2`, pool_size / max_overflow / pool_timeout)

| Connector | Auth | Tests |
|---|---|---|
| `file` | NONE | `backend/tests/unit/test_file_connector.py` |
| `salesforce` | OAUTH2 | `backend/tests/connectors/test_salesforce_connector.py` — SOQL, nextRecordsUrl, upsert |
| `aws-s3` | SERVICE_ACCOUNT | `backend/tests/connectors/test_s3_connector.py` — prefix listing, CSV roundtrip |
| `postgres` | BASIC + SSL | `backend/tests/connectors/test_postgres_connector.py` — SQLite stand-in for INSERT/UPSERT/REPLACE |
| `rest-api` | API_KEY / bearer | `backend/tests/connectors/test_rest_api_connector.py` — offset, cursor, link header; `test_rest_auth.py` |

Registry must list all five: `test_registry_phase2.py`.

## Result log

| Run | Date | lint | typecheck | pytest | Notes |
|---|---|---|---|---|---|
| 1 | 2026-09-21 | pass | pass | 109 passed (unit + connectors) | Salesforce, S3, Postgres, REST registered |
| 2 | 2026-09-21 | pass | pass | 113 passed (unit + connectors) | AgentStudio-aligned Salesforce client, REST auth, S3 session token, postgresql+psycopg2 |

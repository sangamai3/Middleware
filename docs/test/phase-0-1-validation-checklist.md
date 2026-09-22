# Phase 0 + Phase 1 validation checklist

**Date:** 2026-09-21  
**Intent:** Close leftover Phase 0/1 items from `mw-plan.md` after the first implementation pass.

Automated tests: `backend/tests/unit/`. Do not duplicate pytest here.

## How to run

From the repo root:

```bash
./docs/test/run-phase-0-1-validation.sh
```

Equivalent make targets: `make lint`, `make typecheck`, `make test`.

## Phase 0 leftovers — expected evidence

| Item | Evidence |
|---|---|
| `frontend/` layout placeholder | `frontend/README.md` (Phase 5 canvas, not implemented) |
| MIT license | `LICENSE` and `backend/pyproject.toml` `license = {text = "MIT"}` |
| Env template | `.env.example` |
| Google OAuth + JWT routes mounted | `GET /api/v1/auth/google/login`, `POST /api/v1/auth/google/callback`, `GET /api/v1/auth/me` |
| JWT unit coverage | `backend/tests/unit/test_api_routes.py` |

## Phase 1 leftovers — expected evidence

| Item | Evidence |
|---|---|
| Auth handlers (API key, basic, OAuth2+PKCE, service account) | `backend/sangam_mw/connectors/base/auth.py` + `test_auth_handlers.py` |
| OAuth2 refresh 60s before expiry | `ConnectionManager._refresh_oauth_if_needed` + `test_get_handle_refreshes_oauth` |
| JSON Schema config validation | `connectors/base/validation.py`; CLI and connector API reject missing `base_path` |
| Retry RateLimitError / NetworkError | `connectors/base/retry.py` + `test_retry.py` (sleeper injected; no 30s wall clock) |
| FileConnector Excel + JSON write | `test_file_connector.py` |
| CLI `sangam connector list\|test\|preview` | `test_cli.py` |

## Manual FileConnector smoke (optional)

```bash
cd backend
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
sangam connector list
sangam connector test file -c '{"base_path":"/tmp"}'
```

Create a CSV under the `base_path` directory, then:

```bash
sangam connector preview file your.csv -c '{"base_path":"/tmp"}'
```

## Result log

Fill this in when the script is run (CI or local):

| Run | Date | lint | typecheck | pytest | Notes |
|---|---|---|---|---|---|
| 1 | 2026-09-21 | pass | pass | 88 passed | Phase 0/1 leftovers closed: auth handlers, OAuth routes, schema validation, retry, FileConnector Excel |

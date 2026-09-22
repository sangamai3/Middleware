# Test and validation artifacts

Automated pytest lives in `backend/tests/` and is what CI runs.

This folder is for **human-run validation** of a phase: checklists, smoke scripts, and notes you can grep later.

| File | Purpose |
|---|---|
| `phase-0-1-validation-checklist.md` | Phase 0/1 leftover close-out |
| `run-phase-0-1-validation.sh` | Lint, typecheck, full pytest |
| `phase-2-reference-connectors-checklist.md` | Salesforce, S3, Postgres, REST |
| `run-phase-2-validation.sh` | Lint, typecheck, unit + connector tests |

```bash
./docs/test/run-phase-0-1-validation.sh
./docs/test/run-phase-2-validation.sh
```

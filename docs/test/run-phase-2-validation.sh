#!/usr/bin/env bash
# Phase 2 validation: lint, typecheck, unit + connector tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> lint (ruff)"
make lint

echo "==> typecheck (mypy)"
make typecheck

echo "==> pytest (unit + connectors)"
cd backend && pytest tests/unit tests/connectors -v --cov=sangam_mw --cov-report=term-missing

echo "==> Phase 2 validation finished"

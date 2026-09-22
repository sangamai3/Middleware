#!/usr/bin/env bash
# Phase 0/1 validation: lint, typecheck, unit tests.
# Usage (from repo root): ./docs/test/run-phase-0-1-validation.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "==> lint (ruff)"
make lint

echo "==> typecheck (mypy)"
make typecheck

echo "==> pytest + coverage"
make test

echo "==> Phase 0/1 validation finished"

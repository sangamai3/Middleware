"""In-memory run index (dev); executions also persist to Postgres via executor."""

from __future__ import annotations

from ..models.execution import ExecutionRun

_runs: dict[str, ExecutionRun] = {}


def put_run(run: ExecutionRun) -> None:
    _runs[run.run_id] = run


def get_run(run_id: str) -> ExecutionRun | None:
    return _runs.get(run_id)


def list_runs() -> list[ExecutionRun]:
    return list(_runs.values())

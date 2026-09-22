"""
Execution routes — trigger flows and stream results via SSE.

Routes:
  POST /flows/{flow_id}/execute      — trigger a run
  GET  /runs/                        — list recent runs (in-memory)
  GET  /runs/{run_id}                — get run details
  GET  /runs/{run_id}/stream         — SSE stream of FlowEvents
  POST /runs/{run_id}/debug          — AI debug assistant for failed runs
"""

from __future__ import annotations

import asyncio
import textwrap
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ...engine.events import event_bus
from ...engine.executor import FlowExecutor
from ...models.execution import ExecutionRun
from ..auth import get_current_user
from .flows import _flows

router = APIRouter(tags=["executions"])

# In-memory run store for dev/test.
_runs: dict[str, ExecutionRun] = {}


class ExecuteRequest(BaseModel):
    variables: dict[str, Any] = {}
    triggered_by: str | None = None


@router.post("/flows/{flow_id}/execute", response_model=dict)
def execute_flow(
    flow_id: str,
    req: ExecuteRequest,
    _user: dict = Depends(get_current_user),
) -> dict:
    flow = _flows.get(flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    executor = FlowExecutor(bus=event_bus)
    run = executor.execute(
        flow=flow,
        trigger_type="manual",
        triggered_by=req.triggered_by or _user.get("sub"),
        variables=req.variables,
    )
    _runs[run.run_id] = run
    return {
        "run_id": run.run_id,
        "status": run.status,
        "rows_processed": run.rows_processed,
        "error_message": run.error_message,
    }


@router.get("/runs/", response_model=list[dict])
def list_runs(_user: dict = Depends(get_current_user)) -> list[dict]:
    return [
        {
            "run_id": r.run_id,
            "flow_id": r.flow_id,
            "status": r.status,
            "started_at": r.started_at,
        }
        for r in sorted(_runs.values(), key=lambda r: r.started_at or 0, reverse=True)
    ]


@router.get("/runs/{run_id}", response_model=dict)
def get_run(run_id: str, _user: dict = Depends(get_current_user)) -> dict:
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.model_dump()


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    """SSE endpoint — streams FlowEvents for a run as they are emitted."""

    async def _generate():
        subscription = event_bus.subscribe(run_id)
        try:
            async for event in subscription:
                yield event.as_sse()
        except asyncio.CancelledError:
            pass
        finally:
            subscription.close()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/debug")
async def debug_run(
    run_id: str,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """AI-assisted debug for a failed run. Returns a plain-text suggestion."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    failed_steps = [s for s in run.steps if s.status in ("failed", "retrying")]
    if not failed_steps and run.status not in ("failed", "timed_out"):
        return {"suggestion": "This run did not fail — no debug needed.", "confidence": "high"}

    lines: list[str] = [
        f"Flow: {run.flow_id}",
        f"Run status: {run.status}",
        f"Total rows: {run.rows_processed}, failed: {run.rows_failed}",
    ]
    if run.error_message:
        lines.append(f"Top-level error: {run.error_message}")
    for step in failed_steps:
        lines.append(
            f"Step '{step.step_id}' ({step.step_type}) failed: "
            f"{step.error_message or step.error_type or 'unknown error'} "
            f"(retry_count={step.retry_count})"
        )

    context = "\n".join(lines)

    try:
        from ...config import get_settings
        settings = get_settings()
        api_key = getattr(settings, "anthropic_api_key", None)
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        from ...ai.flow_gen import FlowGenerator
        gen = FlowGenerator(api_key=str(api_key), provider="anthropic")
        prompt = textwrap.dedent(f"""
            A SangamMW integration flow has failed. Diagnose the root cause and suggest a fix.

            {context}

            Respond with:
            1. Root cause (1-2 sentences)
            2. Suggested fix (concrete steps)
            3. Prevention tip (optional)
        """).strip()
        suggestion = await gen.raw_complete(prompt)
        return {"suggestion": suggestion, "context": context, "ai_powered": True}
    except Exception as exc:
        return {
            "suggestion": _rule_based_suggestion(failed_steps, run),
            "context": context,
            "ai_powered": False,
            "ai_error": str(exc),
        }


def _rule_based_suggestion(failed_steps: list, run: Any) -> str:
    hints: list[str] = []
    for step in failed_steps:
        err = (step.error_message or step.error_type or "").lower()
        if "timeout" in err:
            hints.append(
                f"Step '{step.step_id}': Timed out. "
                "Consider increasing `timeout_seconds` or reducing batch size."
            )
        elif "auth" in err or "401" in err or "403" in err:
            hints.append(
                f"Step '{step.step_id}': Auth error. "
                "Check that the connection credentials are valid and not expired."
            )
        elif "connection" in err or "connect" in err:
            hints.append(
                f"Step '{step.step_id}': Connection refused. "
                "Verify the host/port in the connection config and that the service is reachable."
            )
        elif "null" in err or "none" in err or "key" in err:
            hints.append(
                f"Step '{step.step_id}': Possible null/missing field. "
                "Check source schema for required fields that may be absent."
            )
        else:
            hints.append(
                f"Step '{step.step_id}' failed with: {step.error_message or 'unknown error'}. "
                "Review the step config and source data."
            )
    if not hints:
        return f"Run {run.run_id} failed. Check the step configs and connection health."
    return "\n\n".join(hints)

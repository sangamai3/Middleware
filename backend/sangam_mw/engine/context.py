"""
ExecutionContext — per-run state: step output cache, variable store, and business event emitter.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ExecutionContext:
    run_id: str
    flow_id: str
    correlation_id: str | None = None
    variables: dict[str, Any] = field(default_factory=dict)
    _outputs: dict[str, pd.DataFrame] = field(default_factory=dict)
    _meta: dict[str, Any] = field(default_factory=dict)
    _current_step_id: str | None = field(default=None, repr=False)

    def set_output(self, step_id: str, df: pd.DataFrame) -> None:
        self._outputs[step_id] = df

    def get_output(self, step_id: str) -> pd.DataFrame:
        if step_id not in self._outputs:
            raise KeyError(f"No output found for step '{step_id}'")
        return self._outputs[step_id]

    def outputs(self) -> dict[str, pd.DataFrame]:
        return dict(self._outputs)

    def set_meta(self, key: str, value: Any) -> None:
        self._meta[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._meta.get(key, default)

    def set_variable(self, name: str, value: Any) -> None:
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        return self.variables.get(name, default)

    def row_counts(self) -> dict[str, int]:
        return {sid: len(df) for sid, df in self._outputs.items()}

    def emit(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Emit a custom business event — stored in BusinessEventTable."""
        try:
            from ..observability.persistence import _emit_business_event
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    _emit_business_event(
                        flow_id=self.flow_id,
                        run_id=self.run_id,
                        step_id=self._current_step_id,
                        correlation_id=self.correlation_id,
                        event_name=event_name,
                        payload=payload or {},
                    )
                )
        except Exception:
            pass

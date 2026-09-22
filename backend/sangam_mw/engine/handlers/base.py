"""Base class for all step handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd

from ..context import ExecutionContext


class StepHandler(ABC):
    """Each step type implements a single execute() method."""

    @abstractmethod
    def execute(
        self,
        config: dict[str, Any],
        context: ExecutionContext,
    ) -> pd.DataFrame | None:
        """
        Execute the step.

        Returns a DataFrame (passed to downstream steps) or None
        for terminal / side-effect steps (writes, notifications, logs).
        """
        ...

    @property
    @abstractmethod
    def step_type(self) -> str:
        """String step type name, e.g. 'connector_read'."""
        ...

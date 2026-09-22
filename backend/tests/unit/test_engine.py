"""Unit tests for Phase 4 Flow Engine."""

from __future__ import annotations

import pytest
import pandas as pd

from sangam_mw.engine.dag import DAGParser
from sangam_mw.engine.context import ExecutionContext
from sangam_mw.engine.events import EventBus, EventType, FlowEvent
from sangam_mw.engine.executor import FlowExecutor
from sangam_mw.engine.validator import FlowValidator
from sangam_mw.models.flow import FlowDefinition, FlowStatus, StepConfig, TriggerType
from sangam_mw.models.execution import RunStatus, StepStatus
from sangam_mw.connectors.base.errors import FlowValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_step(
    id: str,
    step_type: str = "logger",
    depends_on: list[str] | None = None,
    config: dict | None = None,
    optional: bool = False,
) -> StepConfig:
    return StepConfig(
        id=id,
        type=step_type,
        depends_on=depends_on or [],
        config=config or {},
        optional=optional,
    )


def make_flow(steps: list[StepConfig], flow_id: str = "test_flow") -> FlowDefinition:
    return FlowDefinition(
        flow_id=flow_id,
        name="Test Flow",
        steps=steps,
    )


# ---------------------------------------------------------------------------
# DAGParser
# ---------------------------------------------------------------------------


class TestDAGParser:
    def test_linear_chain(self) -> None:
        steps = [
            make_step("a"),
            make_step("b", depends_on=["a"]),
            make_step("c", depends_on=["b"]),
        ]
        parser = DAGParser(steps)
        order = parser.topological_order()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_diamond(self) -> None:
        steps = [
            make_step("a"),
            make_step("b", depends_on=["a"]),
            make_step("c", depends_on=["a"]),
            make_step("d", depends_on=["b", "c"]),
        ]
        parser = DAGParser(steps)
        order = parser.topological_order()
        assert order.index("a") < order.index("d")

    def test_cycle_raises(self) -> None:
        steps = [
            make_step("a", depends_on=["b"]),
            make_step("b", depends_on=["a"]),
        ]
        parser = DAGParser(steps)
        with pytest.raises(FlowValidationError, match="Cycle"):
            parser.topological_order()

    def test_unknown_dep_raises(self) -> None:
        steps = [make_step("a", depends_on=["nonexistent"])]
        parser = DAGParser(steps)
        with pytest.raises(FlowValidationError, match="unknown step"):
            parser.validate()

    def test_parallel_layers(self) -> None:
        steps = [
            make_step("a"),
            make_step("b"),
            make_step("c", depends_on=["a", "b"]),
        ]
        parser = DAGParser(steps)
        layers = parser.parallel_layers()
        assert len(layers) == 2
        # First layer has a and b (no deps); second has c
        assert set(layers[0]) == {"a", "b"}
        assert layers[1] == ["c"]

    def test_single_step(self) -> None:
        steps = [make_step("only")]
        parser = DAGParser(steps)
        assert parser.topological_order() == ["only"]

    def test_empty_graph(self) -> None:
        parser = DAGParser([])
        assert parser.topological_order() == []


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------


class TestExecutionContext:
    def test_set_and_get_output(self) -> None:
        ctx = ExecutionContext(run_id="r1", flow_id="f1")
        df = pd.DataFrame({"v": [1, 2, 3]})
        ctx.set_output("step1", df)
        assert ctx.get_output("step1").equals(df)

    def test_get_missing_output_raises(self) -> None:
        ctx = ExecutionContext(run_id="r1", flow_id="f1")
        with pytest.raises(KeyError):
            ctx.get_output("missing")

    def test_variables(self) -> None:
        ctx = ExecutionContext(run_id="r1", flow_id="f1")
        ctx.set_variable("env", "prod")
        assert ctx.get_variable("env") == "prod"
        assert ctx.get_variable("missing", default="x") == "x"

    def test_row_counts(self) -> None:
        ctx = ExecutionContext(run_id="r1", flow_id="f1")
        ctx.set_output("s1", pd.DataFrame({"v": range(5)}))
        ctx.set_output("s2", pd.DataFrame({"v": range(10)}))
        counts = ctx.row_counts()
        assert counts == {"s1": 5, "s2": 10}


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class TestEventBus:
    def test_emit_and_buffer(self) -> None:
        bus = EventBus(buffer_size=10)
        event = FlowEvent(
            type=EventType.RUN_STARTED,
            run_id="r1",
            flow_id="f1",
        )
        bus.emit(event)
        assert len(bus._buffers["r1"]) == 1

    def test_subscribe_replays_buffered(self) -> None:
        import asyncio

        bus = EventBus(buffer_size=10)
        for i in range(3):
            bus.emit(FlowEvent(type=EventType.LOG, run_id="r2", flow_id="f2", payload={"i": i}))

        sub = bus.subscribe("r2")
        events = []
        for _ in range(3):
            events.append(sub.queue.get_nowait())
        assert len(events) == 3

    def test_sse_format(self) -> None:
        event = FlowEvent(type=EventType.STEP_COMPLETED, run_id="r1", flow_id="f1", step_id="s1")
        sse = event.as_sse()
        assert sse.startswith("data: ")
        assert sse.endswith("\n\n")


# ---------------------------------------------------------------------------
# FlowValidator
# ---------------------------------------------------------------------------


class TestFlowValidator:
    def test_valid_flow(self) -> None:
        flow = make_flow([make_step("a"), make_step("b", depends_on=["a"])])
        validator = FlowValidator(flow)
        warnings = validator.validate()
        assert isinstance(warnings, list)

    def test_cycle_raises(self) -> None:
        flow = make_flow([
            make_step("a", depends_on=["b"]),
            make_step("b", depends_on=["a"]),
        ])
        validator = FlowValidator(flow)
        with pytest.raises(FlowValidationError):
            validator.validate()

    def test_valid_sql_step(self) -> None:
        steps = [
            make_step("src"),
            StepConfig(
                id="sql_step",
                type="transform_sql",
                depends_on=["src"],
                config={"sql": "SELECT 1 AS v", "source_steps": {"src": "src"}},
            ),
        ]
        flow = make_flow(steps)
        validator = FlowValidator(flow)
        warnings = validator.validate()  # should not raise

    def test_invalid_sql_step_raises(self) -> None:
        steps = [
            make_step("src"),
            StepConfig(
                id="sql_step",
                type="transform_sql",
                depends_on=["src"],
                config={"sql": "SELECT @@broken syntax HERE"},
            ),
        ]
        flow = make_flow(steps)
        validator = FlowValidator(flow)
        with pytest.raises(FlowValidationError):
            validator.validate()

    def test_missing_sql_raises(self) -> None:
        steps = [
            StepConfig(id="sql_step", type="transform_sql", config={}),
        ]
        flow = make_flow(steps)
        with pytest.raises(FlowValidationError, match="missing 'sql'"):
            FlowValidator(flow).validate()

    def test_invalid_python_step_raises(self) -> None:
        steps = [
            make_step("src"),
            StepConfig(
                id="py_step",
                type="transform_script",
                depends_on=["src"],
                config={"code": "import os\nresult = df"},
            ),
        ]
        flow = make_flow(steps)
        with pytest.raises(FlowValidationError):
            FlowValidator(flow).validate()

    def test_map_step_missing_fields_raises(self) -> None:
        steps = [
            StepConfig(id="map_step", type="transform_map", config={}),
        ]
        flow = make_flow(steps)
        with pytest.raises(FlowValidationError, match="missing 'fields'"):
            FlowValidator(flow).validate()


# ---------------------------------------------------------------------------
# FlowExecutor (integration with transform handlers)
# ---------------------------------------------------------------------------


class TestFlowExecutor:
    def test_logger_only_flow(self) -> None:
        flow = make_flow([
            make_step("log", step_type="logger", config={"message": "hello", "level": "info"}),
        ])
        bus = EventBus()
        executor = FlowExecutor(bus=bus)
        run = executor.execute(flow)
        assert run.status == RunStatus.SUCCESS

    def test_unknown_step_type_fails(self) -> None:
        flow = make_flow([make_step("bad", step_type="nonexistent_type")])
        executor = FlowExecutor(bus=EventBus())
        run = executor.execute(flow)
        assert run.status == RunStatus.FAILED

    def test_optional_failing_step_does_not_fail_run(self) -> None:
        flow = make_flow([
            make_step("bad", step_type="nonexistent_type", optional=True),
            make_step("log", step_type="logger", config={"message": "ok"}, depends_on=["bad"]),
        ])
        executor = FlowExecutor(bus=EventBus())
        run = executor.execute(flow)
        # The run should succeed because bad step is optional
        assert run.status == RunStatus.SUCCESS

    def test_run_emits_events(self) -> None:
        flow = make_flow([
            make_step("log", step_type="logger", config={"message": "test"}),
        ])
        bus = EventBus()
        executor = FlowExecutor(bus=bus)
        run = executor.execute(flow)
        assert run.run_id in bus._buffers
        types = [e.type for e in bus._buffers[run.run_id]]
        assert EventType.RUN_STARTED in types
        assert EventType.RUN_COMPLETED in types

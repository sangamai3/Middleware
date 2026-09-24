"""Flow Docker Compose generation."""
from __future__ import annotations

from sangam_mw.models.flow import FlowDefinition, StepConfig
from sangam_mw.runtime.flow_compose import analyze_flow, generate_flow_compose


def _csvtest_flow() -> FlowDefinition:
    return FlowDefinition(
        flow_id="flow_csvtest",
        name="CSVTEST",
        steps=[
            StepConfig(
                id="sched",
                type="scheduler",
                config={"cron": "*/5 * * * *"},
            ),
            StepConfig(
                id="read",
                type="connector_read",
                config={
                    "connector_id": "file",
                    "conn": {"connector_id": "file", "base_path": "/data/in"},
                },
                depends_on=["sched"],
            ),
            StepConfig(
                id="write",
                type="connector_write",
                config={
                    "connector_id": "file",
                    "conn": {"connector_id": "file", "base_path": "/data/out"},
                },
                depends_on=["read"],
            ),
        ],
    )


class TestAnalyzeFlow:
    def test_file_connectors_only(self) -> None:
        a = analyze_flow(_csvtest_flow())
        assert a["connector_ids"] == ["file"]
        assert a["pip_extras"] == []
        assert "scheduler" in a["step_types"]
        assert "/data/in" in a["file_paths"]

    def test_kafka_extra(self) -> None:
        flow = FlowDefinition(
            flow_id="f1",
            name="K",
            steps=[
                StepConfig(
                    id="k",
                    type="connector_read",
                    config={"connector_id": "kafka", "conn": {}},
                ),
            ],
        )
        a = analyze_flow(flow)
        assert "kafka" in a["pip_extras"]


class TestGenerateCompose:
    def test_compose_contains_service_and_extras(self) -> None:
        out = generate_flow_compose(_csvtest_flow(), memory_profile="minimal")
        assert "flow-flow-csvtest" in out["compose_yaml"]
        assert "192M" in out["compose_yaml"]
        assert out["manifest"]["pip_extras_arg"] == ""
        assert "Dockerfile.flow-worker" in out["compose_yaml"]

    def test_compose_with_kafka_build_arg(self) -> None:
        flow = FlowDefinition(
            flow_id="f2",
            name="K",
            steps=[
                StepConfig(
                    id="k",
                    type="connector_read",
                    config={"connector_id": "kafka"},
                ),
            ],
        )
        out = generate_flow_compose(flow)
        assert "PIP_EXTRAS: kafka" in out["compose_yaml"] or "kafka" in out["compose_yaml"]

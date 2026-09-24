"""Flow step preview executes upstream steps."""

from pathlib import Path

import pandas as pd

from sangam_mw.engine.executor import FlowExecutor
from sangam_mw.models.flow import FlowDefinition, StepConfig


def test_preview_runs_upstream_through_format_convert(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    pd.DataFrame({"id": [1, 2], "name": ["a", "b"]}).to_csv(in_dir / "data.csv", index=False)

    flow = FlowDefinition(
        flow_id="f1",
        name="test",
        steps=[
            StepConfig(
                id="src",
                type="connector_read",
                config={
                    "connector_id": "file",
                    "conn": {"base_path": str(in_dir)},
                    "object": "data.csv",
                },
                depends_on=[],
            ),
            StepConfig(
                id="fmt",
                type="transform_format",
                config={"input_format": "csv", "output_format": "json"},
                depends_on=["src"],
            ),
        ],
    )
    executor = FlowExecutor()
    result = executor.preview(flow, "fmt", limit=10)
    assert result.get("error") is None
    assert result["row_count"] == 2
    assert len(result["rows"]) == 2
    assert "name" in result["rows"][0]
    assert result["steps_executed"] == ["Source · File · data.csv", "Format Convert"]
    assert result.get("output_format") == "json"
    assert result.get("formatted_output", {}).get("format") == "json"
    assert '"id"' in result["formatted_output"]["content"]

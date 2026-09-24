from sangam_mw.engine.step_display import step_display_name
from sangam_mw.models.flow import StepConfig


def test_connector_read_default_label() -> None:
    step = StepConfig(
        id="node_1",
        type="connector_read",
        config={"connector_id": "file", "object": "*.csv"},
    )
    assert step_display_name(step) == "Source · File · *.csv"


def test_connector_read_custom_step_name() -> None:
    step = StepConfig(
        id="node_1",
        type="connector_read",
        config={"label": "Orders in", "connector_id": "file", "object": "orders_a.csv"},
    )
    assert step_display_name(step) == "Orders in · File · orders_a.csv"


def test_transform_step() -> None:
    step = StepConfig(id="n2", type="transform_format", config={})
    assert step_display_name(step) == "Format Convert"

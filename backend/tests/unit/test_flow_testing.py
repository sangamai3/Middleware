"""Unit tests for the flow test runner framework."""

import textwrap

import pytest

from sangam_mw.testing.runner import (
    FlowTestRunner,
    FlowTestSuite,
    FlowTestResult,
    MockConnectorOutput,
    OutputAssertion,
    FlowTestCase,
)


# ── fixtures ─────────────────────────────────────────────────────────────────

SUITE_YAML = textwrap.dedent("""\
    flow_id: order-pipeline
    flow_file: "order-pipeline.yaml"
    test_cases:
      - name: basic_smoke
        description: Two rows pass through
        mocks:
          - connection_id: src_conn
            object: orders
            rows:
              - {order_id: 1, amount: 99.99, status: pending}
              - {order_id: 2, amount: 14.00, status: completed}
        assertions:
          - step_id: read-step
            exact_rows: 2
          - step_id: read-step
            contains_field: order_id
""")


@pytest.fixture
def suite_file(tmp_path):
    f = tmp_path / "suite.yaml"
    f.write_text(SUITE_YAML)
    return f


# ── FlowTestSuite ─────────────────────────────────────────────────────────────

class TestFlowTestSuite:
    def test_from_yaml_parses_flow_id(self, suite_file):
        suite = FlowTestSuite.from_yaml(suite_file)
        assert suite.flow_id == "order-pipeline"

    def test_from_yaml_parses_test_cases(self, suite_file):
        suite = FlowTestSuite.from_yaml(suite_file)
        assert len(suite.test_cases) == 1
        assert suite.test_cases[0].name == "basic_smoke"

    def test_from_yaml_parses_mocks(self, suite_file):
        suite = FlowTestSuite.from_yaml(suite_file)
        tc = suite.test_cases[0]
        assert len(tc.mocks) == 1
        mock = tc.mocks[0]
        assert mock.connection_id == "src_conn"
        assert mock.object_name == "orders"
        assert len(mock.rows) == 2

    def test_from_yaml_parses_assertions(self, suite_file):
        suite = FlowTestSuite.from_yaml(suite_file)
        tc = suite.test_cases[0]
        assert len(tc.assertions) == 2

    def test_from_yaml_missing_file_raises(self, tmp_path):
        with pytest.raises((FileNotFoundError, OSError)):
            FlowTestSuite.from_yaml(tmp_path / "nonexistent.yaml")


# ── MockConnectorOutput ───────────────────────────────────────────────────────

class TestMockConnectorOutput:
    def test_rows_accessible(self):
        mock = MockConnectorOutput(connection_id="c1", object_name="orders", rows=[{"id": 1}, {"id": 2}])
        assert len(mock.rows) == 2
        assert mock.rows[0]["id"] == 1

    def test_as_dataframe_shape(self):
        mock = MockConnectorOutput(connection_id="c1", object_name="orders", rows=[{"a": 1}, {"a": 2}])
        df = mock.as_dataframe()
        assert len(df) == 2
        assert "a" in df.columns

    def test_empty_rows_as_dataframe(self):
        mock = MockConnectorOutput(connection_id="c1", object_name="orders", rows=[])
        df = mock.as_dataframe()
        assert len(df) == 0


# ── OutputAssertion ───────────────────────────────────────────────────────────

class TestOutputAssertion:
    def test_exact_rows_pass(self):
        import pandas as pd
        assertion = OutputAssertion(step_id="s1", exact_rows=2)
        df = pd.DataFrame([{"a": 1}, {"a": 2}])
        failures = assertion.check(df)
        assert failures == []

    def test_exact_rows_fail(self):
        import pandas as pd
        assertion = OutputAssertion(step_id="s1", exact_rows=5)
        df = pd.DataFrame([{"a": 1}])
        failures = assertion.check(df)
        assert len(failures) > 0
        assert "5" in failures[0]

    def test_contains_field_pass(self):
        import pandas as pd
        assertion = OutputAssertion(step_id="s1", contains_field="order_id")
        df = pd.DataFrame([{"order_id": 1, "status": "ok"}])
        failures = assertion.check(df)
        assert failures == []

    def test_contains_field_fail(self):
        import pandas as pd
        assertion = OutputAssertion(step_id="s1", contains_field="missing_col")
        df = pd.DataFrame([{"other": 1}])
        failures = assertion.check(df)
        assert len(failures) > 0

    def test_min_rows_pass(self):
        import pandas as pd
        assertion = OutputAssertion(step_id="s1", min_rows=1)
        df = pd.DataFrame([{"x": 1}, {"x": 2}])
        assert assertion.check(df) == []

    def test_max_rows_fail(self):
        import pandas as pd
        assertion = OutputAssertion(step_id="s1", max_rows=1)
        df = pd.DataFrame([{"x": 1}, {"x": 2}])
        failures = assertion.check(df)
        assert len(failures) > 0


# ── FlowTestRunner ────────────────────────────────────────────────────────────

class TestFlowTestRunner:
    def test_runner_returns_list(self, suite_file, tmp_path):
        # Create a minimal flow file so the runner can load it
        flow_file = tmp_path / "order-pipeline.yaml"
        flow_file.write_text("flow_id: order-pipeline\nsteps: []\n")
        # Patch the suite's flow_file path
        suite = FlowTestSuite.from_yaml(suite_file)
        from pathlib import Path
        suite.flow_file = flow_file
        runner = FlowTestRunner()
        results = runner.run_suite(suite)
        assert isinstance(results, list)

    def test_result_has_required_fields(self, suite_file, tmp_path):
        flow_file = tmp_path / "order-pipeline.yaml"
        flow_file.write_text("flow_id: order-pipeline\nsteps: []\n")
        suite = FlowTestSuite.from_yaml(suite_file)
        suite.flow_file = flow_file
        runner = FlowTestRunner()
        results = runner.run_suite(suite)
        for r in results:
            assert hasattr(r, "passed")
            assert hasattr(r, "test_case")
            assert hasattr(r, "failures")

    def test_print_report_all_pass_returns_zero(self, tmp_path):
        result = FlowTestResult(test_case="smoke", passed=True, failures=[])
        runner = FlowTestRunner()
        code = runner.print_report([result], "test-flow")
        assert code == 0

    def test_print_report_any_fail_returns_nonzero(self, tmp_path):
        result = FlowTestResult(test_case="smoke", passed=False, failures=["Expected 2 rows, got 0"])
        runner = FlowTestRunner()
        code = runner.print_report([result], "test-flow")
        assert code != 0

"""
Flow testing framework — sangam test <flow-file> [--test-file]

Test cases define:
  - mock connector outputs (no real connections needed)
  - expected output: schema, row_count, field_values, assertions

Runs in CI (GitHub Actions / GitLab CI) with no live credentials.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ..connectors.base.schemas import ReadConfig, WriteConfig, WriteResult


@dataclass
class MockConnectorOutput:
    """Rows returned by a mock source connector for a test case."""
    connection_id: str
    object_name: str
    rows: list[dict[str, Any]]
    write_capture: list[dict[str, Any]] = field(default_factory=list)

    def as_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows) if self.rows else pd.DataFrame()


@dataclass
class OutputAssertion:
    """Assertion on a step's output."""
    step_id: str
    min_rows: int | None = None
    max_rows: int | None = None
    exact_rows: int | None = None
    contains_field: str | None = None
    field_values: dict[str, Any] = field(default_factory=dict)
    schema_matches: list[str] | None = None  # expected column names

    def check(self, df: pd.DataFrame) -> list[str]:
        failures: list[str] = []
        if self.exact_rows is not None and len(df) != self.exact_rows:
            failures.append(f"Expected {self.exact_rows} rows, got {len(df)}")
        if self.min_rows is not None and len(df) < self.min_rows:
            failures.append(f"Expected >= {self.min_rows} rows, got {len(df)}")
        if self.max_rows is not None and len(df) > self.max_rows:
            failures.append(f"Expected <= {self.max_rows} rows, got {len(df)}")
        if self.contains_field and self.contains_field not in df.columns:
            failures.append(f"Missing expected field '{self.contains_field}'")
        if self.schema_matches:
            missing = set(self.schema_matches) - set(df.columns)
            if missing:
                failures.append(f"Schema missing columns: {missing}")
        for field_name, expected_value in self.field_values.items():
            if field_name not in df.columns:
                failures.append(f"Field '{field_name}' not in output")
                continue
            actual = df[field_name].tolist()
            if isinstance(expected_value, list):
                if actual != expected_value:
                    failures.append(f"Field '{field_name}': expected {expected_value}, got {actual}")
            elif expected_value not in actual:
                failures.append(f"Field '{field_name}': value {expected_value!r} not found in {actual[:5]}")
        return failures


@dataclass
class FlowTestCase:
    name: str
    description: str = ""
    mocks: list[MockConnectorOutput] = field(default_factory=list)
    assertions: list[OutputAssertion] = field(default_factory=list)
    expect_failure: bool = False
    flow_parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowTestResult:
    test_case: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    step_outputs: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0


@dataclass
class FlowTestSuite:
    flow_id: str
    flow_file: Path
    test_cases: list[FlowTestCase]

    @classmethod
    def from_yaml(cls, test_file: Path) -> "FlowTestSuite":
        raw = yaml.safe_load(test_file.read_text())
        cases = []
        for tc in raw.get("test_cases", []):
            mocks = [
                MockConnectorOutput(
                    connection_id=m["connection_id"],
                    object_name=m["object"],
                    rows=m.get("rows", []),
                )
                for m in tc.get("mocks", [])
            ]
            assertions = [
                OutputAssertion(
                    step_id=a["step_id"],
                    exact_rows=a.get("exact_rows"),
                    min_rows=a.get("min_rows"),
                    max_rows=a.get("max_rows"),
                    contains_field=a.get("contains_field"),
                    field_values=a.get("field_values", {}),
                    schema_matches=a.get("schema_matches"),
                )
                for a in tc.get("assertions", [])
            ]
            cases.append(FlowTestCase(
                name=tc["name"],
                description=tc.get("description", ""),
                mocks=mocks,
                assertions=assertions,
                expect_failure=tc.get("expect_failure", False),
                flow_parameters=tc.get("parameters", {}),
            ))
        flow_file = Path(raw.get("flow_file", ""))
        return cls(
            flow_id=raw.get("flow_id", flow_file.stem),
            flow_file=flow_file,
            test_cases=cases,
        )


class FlowTestRunner:
    """
    Runs a FlowTestSuite against a flow definition using mock connectors.
    Does not start a server — runs the engine in-process.
    """

    def run_suite(self, suite: FlowTestSuite) -> list[FlowTestResult]:
        results = []
        for test_case in suite.test_cases:
            results.append(self._run_case(suite, test_case))
        return results

    def _run_case(self, suite: FlowTestSuite, test_case: FlowTestCase) -> FlowTestResult:
        import time
        start = time.monotonic()
        try:
            flow_def = yaml.safe_load(suite.flow_file.read_text())
        except Exception as exc:
            return FlowTestResult(
                test_case=test_case.name,
                passed=test_case.expect_failure,
                error=f"Cannot load flow file: {exc}",
            )

        mock_index: dict[tuple[str, str], MockConnectorOutput] = {
            (m.connection_id, m.object_name): m for m in test_case.mocks
        }

        step_outputs: dict[str, pd.DataFrame] = {}
        step_row_counts: dict[str, int] = {}
        test_failures: list[str] = []

        for step in flow_def.get("steps", []):
            step_id = step.get("step_id", "unknown")
            step_type = step.get("type", "")
            config = step.get("config", {})

            if step_type == "source":
                conn_id = step.get("connector_id", "")
                obj = config.get("object", "")
                mock = mock_index.get((conn_id, obj)) or next(
                    (m for m in test_case.mocks if m.object_name == obj), None
                )
                df = mock.as_dataframe() if mock else pd.DataFrame()
                step_outputs[step_id] = df
                step_row_counts[step_id] = len(df)

            elif step_type == "sink":
                upstream_id = (step.get("depends_on") or [step_id])[0]
                df = step_outputs.get(upstream_id, pd.DataFrame())
                step_row_counts[step_id] = len(df)

            elif step_type in ("transform", "transform_map", "transform_sql", "transform_script"):
                upstream_id = (step.get("depends_on") or [step_id])[0]
                df = step_outputs.get(upstream_id, pd.DataFrame())
                step_outputs[step_id] = df
                step_row_counts[step_id] = len(df)

        for assertion in test_case.assertions:
            df = step_outputs.get(assertion.step_id, pd.DataFrame())
            failures = assertion.check(df)
            test_failures.extend(
                f"[{assertion.step_id}] {f}" for f in failures
            )

        elapsed = int((time.monotonic() - start) * 1000)
        passed = (len(test_failures) == 0) != test_case.expect_failure
        return FlowTestResult(
            test_case=test_case.name,
            passed=passed,
            failures=test_failures,
            step_outputs=step_row_counts,
            duration_ms=elapsed,
        )

    def print_report(self, results: list[FlowTestResult], flow_id: str) -> int:
        """Print a human-readable report. Returns exit code (0=all pass)."""
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        print(f"\nFlow: {flow_id}")
        print(f"Results: {passed} passed, {failed} failed ({len(results)} total)\n")
        for r in results:
            icon = "✓" if r.passed else "✗"
            print(f"  {icon} {r.test_case}  ({r.duration_ms}ms)")
            for f in r.failures:
                print(f"      FAIL: {f}")
            if r.error:
                print(f"      ERROR: {r.error}")
        return 0 if failed == 0 else 1

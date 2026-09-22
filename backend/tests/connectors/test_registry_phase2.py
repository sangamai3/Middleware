"""Entry-point discovery for Phase 2 reference connectors."""

from sangam_mw.connectors.base.registry import ConnectorRegistry


def test_registry_loads_all_phase2_connectors() -> None:
    registry = ConnectorRegistry()
    registry.load()
    ids = set(registry.ids())
    assert {
        "file",
        "salesforce",
        "aws-s3",
        "postgres",
        "rest-api",
    }.issubset(ids)

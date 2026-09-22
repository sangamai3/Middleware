"""Unit tests for OAS 3.0 parser and exporter."""

import pytest
import yaml

from sangam_mw.oas.spec import FlowToOas, OasExporter, OasParser


MINIMAL_OAS = {
    "openapi": "3.0.3",
    "info": {"title": "Acme API", "version": "1.0.0"},
    "paths": {
        "/orders": {
            "get": {
                "operationId": "listOrders",
                "summary": "List orders",
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "operationId": "createOrder",
                "summary": "Create order",
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}}}
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/orders/{id}": {
            "get": {
                "operationId": "getOrder",
                "summary": "Get order",
                "parameters": [{"name": "id", "in": "path", "required": True}],
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
}


@pytest.fixture
def parser():
    return OasParser()


class TestOasParser:
    def test_parse_returns_api_product(self, parser):
        product = parser.parse(MINIMAL_OAS)
        assert product.name == "Acme API"
        assert product.version == "1.0.0"

    def test_endpoints_extracted(self, parser):
        product = parser.parse(MINIMAL_OAS)
        paths = {e.path for e in product.endpoints}
        assert "/orders" in paths
        assert "/orders/{id}" in paths

    def test_methods_extracted(self, parser):
        product = parser.parse(MINIMAL_OAS)
        ops = {(e.path, e.method.upper()) for e in product.endpoints}
        assert ("/orders", "GET") in ops
        assert ("/orders", "POST") in ops
        assert ("/orders/{id}", "GET") in ops

    def test_operation_ids_become_flow_ids(self, parser):
        product = parser.parse(MINIMAL_OAS)
        flow_ids = {e.flow_id for e in product.endpoints}
        assert "listOrders" in flow_ids
        assert "createOrder" in flow_ids

    def test_endpoint_count(self, parser):
        product = parser.parse(MINIMAL_OAS)
        assert len(product.endpoints) == 3

    def test_generate_flow_skeleton_is_valid_yaml(self, parser):
        skeleton_yaml = parser.generate_flow_skeleton(MINIMAL_OAS, "listOrders")
        parsed = yaml.safe_load(skeleton_yaml)
        assert isinstance(parsed, dict)
        assert "flow_id" in parsed

    def test_generate_flow_skeleton_references_operation(self, parser):
        skeleton_yaml = parser.generate_flow_skeleton(MINIMAL_OAS, "createOrder")
        assert "createOrder" in skeleton_yaml


class TestOasExporter:
    def test_export_returns_dict(self):
        product = OasParser().parse(MINIMAL_OAS)
        oas_dict = OasExporter().export(product)
        assert isinstance(oas_dict, dict)
        assert oas_dict.get("openapi", "").startswith("3.")

    def test_to_yaml_roundtrip(self):
        product = OasParser().parse(MINIMAL_OAS)
        oas_yaml = OasExporter().to_yaml(product)
        reparsed = yaml.safe_load(oas_yaml)
        assert "paths" in reparsed

    def test_paths_preserved(self):
        product = OasParser().parse(MINIMAL_OAS)
        oas_dict = OasExporter().export(product)
        assert "/orders" in oas_dict.get("paths", {})


class TestFlowToOas:
    def test_extracts_path_from_api_gateway_flow(self):
        flow_def = {
            "flow_id": "listOrders",
            "trigger": {"type": "api_gateway", "path": "/orders", "method": "GET"},
            "steps": [],
        }
        result = FlowToOas().extract_path(flow_def)
        # returns {"/orders": {"get": {operationId, ...}}}
        assert isinstance(result, dict)
        assert "/orders" in result
        assert "get" in result["/orders"]
        assert result["/orders"]["get"]["operationId"] == "listOrders"

    def test_returns_none_for_non_gateway_flow(self):
        flow_def = {
            "flow_id": "scheduleJob",
            "trigger": {"type": "schedule", "cron": "0 * * * *"},
            "steps": [],
        }
        result = FlowToOas().extract_path(flow_def)
        assert result is None

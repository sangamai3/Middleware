"""Kafka connector — produce and consume messages via confluent-kafka."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pandas as pd

from ..base.connector import BaseConnector, SinkMixin, SourceMixin
from ..base.errors import ConnectorValidationError, DataReadError, NetworkError
from ..base.metadata import AuthType, ConnectorMetadata, OperationType
from ..base.schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)

try:
    from confluent_kafka import Consumer, Producer, KafkaError, TopicPartition  # type: ignore[import]
    from confluent_kafka.admin import AdminClient  # type: ignore[import]
    _HAS_KAFKA = True
except ImportError:
    _HAS_KAFKA = False


def _require_kafka() -> None:
    if not _HAS_KAFKA:
        raise ImportError("confluent-kafka is required: pip install confluent-kafka")


class KafkaConnector(BaseConnector, SourceMixin, SinkMixin):
    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            connector_id="kafka",
            label="Apache Kafka",
            family="messaging",
            version="1.0.0",
            auth_type=AuthType.BASIC,
            operations=[OperationType.READ, OperationType.WRITE],
            description="Read from and write to Apache Kafka topics.",
            connection_schema={
                "type": "object",
                "required": ["bootstrap_servers"],
                "properties": {
                    "bootstrap_servers": {
                        "type": "string",
                        "description": "Comma-separated host:port list",
                    },
                    "security_protocol": {
                        "type": "string",
                        "enum": ["PLAINTEXT", "SSL", "SASL_PLAINTEXT", "SASL_SSL"],
                        "default": "PLAINTEXT",
                    },
                    "sasl_mechanism": {
                        "type": "string",
                        "enum": ["PLAIN", "SCRAM-SHA-256", "SCRAM-SHA-512"],
                        "default": "PLAIN",
                    },
                    "sasl_username": {"type": "string"},
                    "sasl_password": {"type": "string", "secret": True},
                    "ssl_ca_location": {"type": "string"},
                    "group_id": {
                        "type": "string",
                        "default": "sangam-mw",
                        "description": "Consumer group ID",
                    },
                },
            },
            read_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string", "description": "Topic name"},
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "Max messages to consume",
                    },
                    "timeout_seconds": {"type": "number", "default": 10.0},
                    "offset": {
                        "type": "string",
                        "enum": ["earliest", "latest"],
                        "default": "latest",
                    },
                    "value_format": {
                        "type": "string",
                        "enum": ["json", "string", "bytes"],
                        "default": "json",
                    },
                },
            },
            write_schema={
                "type": "object",
                "required": ["object"],
                "properties": {
                    "object": {"type": "string", "description": "Topic name"},
                    "key_field": {
                        "type": "string",
                        "description": "Column to use as message key",
                    },
                    "value_format": {
                        "type": "string",
                        "enum": ["json", "string"],
                        "default": "json",
                    },
                    "compression": {
                        "type": "string",
                        "enum": ["none", "gzip", "snappy", "lz4"],
                        "default": "none",
                    },
                },
            },
        )

    def _kafka_conf(self, handle: ConnectionHandle) -> dict[str, Any]:
        cfg = handle.config
        conf: dict[str, Any] = {
            "bootstrap.servers": cfg["bootstrap_servers"],
        }
        proto = cfg.get("security_protocol", "PLAINTEXT")
        if proto != "PLAINTEXT":
            conf["security.protocol"] = proto
        if proto in ("SASL_PLAINTEXT", "SASL_SSL"):
            conf["sasl.mechanism"] = cfg.get("sasl_mechanism", "PLAIN")
            conf["sasl.username"] = cfg.get("sasl_username", "")
            conf["sasl.password"] = cfg.get("sasl_password", "")
        if cfg.get("ssl_ca_location"):
            conf["ssl.ca.location"] = cfg["ssl_ca_location"]
        return conf

    def test_connection(self, handle: ConnectionHandle) -> bool:
        _require_kafka()
        try:
            admin = AdminClient(self._kafka_conf(handle))
            meta = admin.list_topics(timeout=5)
            return meta is not None
        except Exception as exc:
            raise NetworkError(f"Kafka connection failed: {exc}") from exc

    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]:
        _require_kafka()
        try:
            admin = AdminClient(self._kafka_conf(handle))
            meta = admin.list_topics(timeout=10)
            return [
                ObjectSchema(name=t, kind="topic")
                for t in sorted(meta.topics.keys())
                if not t.startswith("__")
            ]
        except Exception as exc:
            raise DataReadError(f"Cannot list topics: {exc}") from exc

    def introspect_columns(self, handle: ConnectionHandle, object_name: str) -> list[ColumnSchema]:
        return [
            ColumnSchema(name="_key", data_type="string", nullable=True),
            ColumnSchema(name="_value", data_type="string", nullable=False),
            ColumnSchema(name="_partition", data_type="integer", nullable=False),
            ColumnSchema(name="_offset", data_type="integer", nullable=False),
            ColumnSchema(name="_timestamp", data_type="timestamp", nullable=True),
        ]

    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame:
        _require_kafka()
        topic = config.object
        limit = config.limit or 100
        timeout = float(config.extra.get("timeout_seconds", 10.0))
        offset_reset = config.extra.get("offset", "latest")
        value_format = config.extra.get("value_format", "json")

        conf = self._kafka_conf(handle)
        conf["group.id"] = handle.config.get("group_id", "sangam-mw")
        conf["auto.offset.reset"] = offset_reset
        conf["enable.auto.commit"] = False

        consumer = Consumer(conf)
        try:
            consumer.subscribe([topic])
            rows: list[dict[str, Any]] = []
            while len(rows) < limit:
                msg = consumer.poll(timeout=timeout)
                if msg is None:
                    break
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        break
                    raise DataReadError(f"Kafka error: {msg.error()}")
                raw_value = msg.value()
                value: Any
                if value_format == "json" and raw_value:
                    import json
                    try:
                        value = json.loads(raw_value)
                    except Exception:
                        value = raw_value.decode("utf-8", errors="replace")
                elif value_format == "string":
                    value = raw_value.decode("utf-8", errors="replace") if raw_value else None
                else:
                    value = raw_value
                key_raw = msg.key()
                rows.append({
                    "_key": key_raw.decode("utf-8", errors="replace") if key_raw else None,
                    "_value": value,
                    "_partition": msg.partition(),
                    "_offset": msg.offset(),
                    "_timestamp": msg.timestamp()[1] if msg.timestamp()[0] != 0 else None,
                })
        finally:
            consumer.close()

        if not rows:
            return pd.DataFrame(columns=["_key", "_value", "_partition", "_offset", "_timestamp"])
        return pd.DataFrame(rows)

    def read_batch(self, handle: ConnectionHandle, config: ReadConfig) -> Iterator[pd.DataFrame]:
        yield self.read(handle, config)

    def write(self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig) -> WriteResult:
        _require_kafka()
        import json

        topic = config.object
        key_field = config.extra.get("key_field")
        value_format = config.extra.get("value_format", "json")
        compression = config.extra.get("compression", "none")

        conf = self._kafka_conf(handle)
        conf["compression.type"] = compression

        producer = Producer(conf)
        delivered = 0
        failed = 0
        errors: list[dict[str, Any]] = []

        def delivery_report(err: Any, _msg: Any) -> None:
            nonlocal delivered, failed
            if err:
                failed += 1
                errors.append({"error": str(err)})
            else:
                delivered += 1

        try:
            for row in df.to_dict(orient="records"):
                key_bytes: bytes | None = None
                if key_field and key_field in row:
                    key_bytes = str(row[key_field]).encode()
                if value_format == "json":
                    value_bytes = json.dumps(row).encode()
                else:
                    value_col = "_value" if "_value" in row else next(iter(row))
                    value_bytes = str(row[value_col]).encode()
                producer.produce(topic, value=value_bytes, key=key_bytes, callback=delivery_report)
            producer.flush(timeout=30)
        except Exception as exc:
            raise NetworkError(f"Kafka produce failed: {exc}") from exc

        return WriteResult(rows_written=delivered, rows_failed=failed, errors=errors)

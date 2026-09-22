from abc import ABC, abstractmethod
from collections.abc import Iterator

import pandas as pd

from .metadata import ConnectorMetadata
from .schemas import (
    ColumnSchema,
    ConnectionHandle,
    ObjectSchema,
    ReadConfig,
    WriteConfig,
    WriteResult,
)


class BaseConnector(ABC):
    """
    Minimum contract every connector must implement.

    A connector that only reads implements BaseConnector + SourceMixin.
    A connector that only writes implements BaseConnector + SinkMixin.
    A bidirectional connector implements all three.
    """

    @property
    @abstractmethod
    def metadata(self) -> ConnectorMetadata: ...

    @abstractmethod
    def test_connection(self, handle: ConnectionHandle) -> bool: ...

    @abstractmethod
    def introspect_objects(self, handle: ConnectionHandle) -> list[ObjectSchema]: ...

    @abstractmethod
    def introspect_columns(
        self, handle: ConnectionHandle, object_name: str
    ) -> list[ColumnSchema]: ...

    def sample(self, handle: ConnectionHandle, object_name: str, limit: int = 10) -> pd.DataFrame:
        if not isinstance(self, SourceMixin):
            raise TypeError(f"{self.__class__.__name__} does not support reading")
        return self.read(handle, ReadConfig(object=object_name, limit=limit))


class SourceMixin(ABC):
    @abstractmethod
    def read(self, handle: ConnectionHandle, config: ReadConfig) -> pd.DataFrame: ...

    def read_batch(self, handle: ConnectionHandle, config: ReadConfig) -> Iterator[pd.DataFrame]:
        """Default: single batch. Connectors override for server-side pagination."""
        yield self.read(handle, config)


class SinkMixin(ABC):
    @abstractmethod
    def write(
        self, df: pd.DataFrame, handle: ConnectionHandle, config: WriteConfig
    ) -> WriteResult: ...

    def write_batch(
        self,
        iterator: Iterator[pd.DataFrame],
        handle: ConnectionHandle,
        config: WriteConfig,
    ) -> WriteResult:
        """Default: concat all batches then write once. Connectors override for streaming."""
        return self.write(pd.concat(list(iterator)), handle, config)

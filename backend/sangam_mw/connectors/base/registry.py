import logging
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .connector import BaseConnector

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "sangam_mw.connectors"


class ConnectorRegistry:
    """
    Discovers connectors via Python entry-points.

    Third-party connectors register themselves by installing a package that declares:
        [project.entry-points."sangam_mw.connectors"]
        my_connector = "my_package.connector:MyConnector"

    Then `pip install sangam-mw-my-connector` makes it available here.
    """

    def __init__(self) -> None:
        self._connectors: dict[str, type[BaseConnector]] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        eps = entry_points(group=_ENTRY_POINT_GROUP)
        for ep in eps:
            try:
                cls = ep.load()
                instance = cls()
                self._connectors[instance.metadata.connector_id] = cls
                logger.debug("Loaded connector: %s", instance.metadata.connector_id)
            except Exception as exc:
                logger.warning("Failed to load connector %s: %s", ep.name, exc)
        self._loaded = True

    def get(self, connector_id: str) -> "BaseConnector":
        if not self._loaded:
            self.load()
        cls = self._connectors.get(connector_id)
        if not cls:
            available = list(self._connectors.keys())
            raise KeyError(f"Connector '{connector_id}' not found. Available: {available}")
        return cls()

    def all(self) -> list["BaseConnector"]:
        if not self._loaded:
            self.load()
        return [cls() for cls in self._connectors.values()]

    def ids(self) -> list[str]:
        if not self._loaded:
            self.load()
        return list(self._connectors.keys())


registry = ConnectorRegistry()

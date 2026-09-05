"""An in-memory record store, including a nested class and inheritance."""

from typing import Dict, List, Optional


class RecordError(Exception):
    """Raised when a record cannot be found or stored."""


class Store:
    """Keeps records in a dictionary keyed by id."""

    class Config:
        """Nested configuration for a Store instance."""

        def defaults(self) -> dict:
            """Return the default configuration mapping."""
            return {"max_records": 100}

    def __init__(self) -> None:
        self._records: Dict[str, dict] = {}

    def put(self, key: str, value: dict) -> None:
        """Insert or replace a record."""
        self._records[key] = value

    def get(self, key: str) -> Optional[dict]:
        """Fetch a record, or None when it is absent."""
        return self._records.get(key)

    def require(self, key: str) -> dict:
        """Fetch a record, raising RecordError when it is absent."""
        record = self.get(key)
        if record is None:
            raise RecordError(f"no record for {key!r}")
        return record

    def keys(self) -> List[str]:
        """List every stored key in insertion order."""
        return list(self._records)


class AuditedStore(Store):
    """A Store that records every write to an in-memory log."""

    def __init__(self) -> None:
        super().__init__()
        self.log: List[str] = []

    def put(self, key: str, value: dict) -> None:
        """Insert a record and append the key to the audit log."""
        self.log.append(key)
        super().put(key, value)

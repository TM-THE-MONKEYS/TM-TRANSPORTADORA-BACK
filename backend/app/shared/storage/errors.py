"""Storage backend errors (not HTTP-layer exceptions)."""
from __future__ import annotations


class StorageObjectNotFoundError(Exception):
    """Object missing in the active storage backend."""

    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path
        super().__init__(f"Object not found: {storage_path}")


class StorageBackendError(Exception):
    """Supabase or local storage operation failed."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        status_code: int | None = None,
        storage_path: str | None = None,
    ) -> None:
        self.message = message
        self.operation = operation
        self.status_code = status_code
        self.storage_path = storage_path
        super().__init__(message)

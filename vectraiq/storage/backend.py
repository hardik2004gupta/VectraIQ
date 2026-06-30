"""Storage backend abstraction and factory."""

from abc import ABC, abstractmethod

from vectraiq.config import settings


class StorageBackend(ABC):
    """Generic byte storage interface used by document cache services."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True when key exists."""

    @abstractmethod
    def save_bytes(self, key: str, data: bytes) -> None:
        """Persist bytes at key."""

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        """Read bytes for key. Raises FileNotFoundError if key does not exist."""

    @abstractmethod
    def url_for(self, key: str) -> str:
        """Return a stable URL-like reference for key."""


def get_storage_backend() -> StorageBackend:
    """Build a configured storage backend from settings."""
    backend = settings.storage_backend.strip().lower()
    if backend == "local":
        from vectraiq.storage.local import LocalStorage
        return LocalStorage()
    if backend == "s3":
        from vectraiq.storage.s3 import S3Storage
        return S3Storage()
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend!r}")

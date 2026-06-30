"""Local filesystem storage backend.

Stores files under a configurable base directory (default: .vectraiq_storage/).
"""

from __future__ import annotations

import os
from pathlib import Path

from vectraiq.storage.backend import StorageBackend

_DEFAULT_BASE = ".vectraiq_storage"


class LocalStorage(StorageBackend):
    """Stores bytes on the local filesystem under base_dir."""

    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(
            base_dir
            or os.getenv("LOCAL_STORAGE_PATH", _DEFAULT_BASE)
        )
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        # Sanitize key: strip leading slashes to prevent path traversal
        safe_key = key.lstrip("/").lstrip("\\")
        path = (self.base_dir / safe_key).resolve()
        # Ensure resolved path is still under base_dir
        if not str(path).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"Key {key!r} resolves outside the storage directory")
        return path

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def save_bytes(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read_bytes(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.exists():
            raise FileNotFoundError(f"Key not found in local storage: {key!r}")
        return path.read_bytes()

    def url_for(self, key: str) -> str:
        return str(self._resolve(key))

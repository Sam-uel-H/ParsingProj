from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    content_type: str
    size: int


class ObjectNotFoundError(KeyError):
    """Raised when an object key does not exist."""


class ObjectStorage(ABC):
    @abstractmethod
    async def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        """Store bytes at a caller-owned key."""

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Load bytes or raise ObjectNotFoundError."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return whether a key exists."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a key; missing keys are ignored."""


class FileSystemObjectStorage(ObjectStorage):
    """Local-development storage rooted in one configured directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        normalized = PurePosixPath(key.replace("\\", "/"))
        if normalized.is_absolute() or not normalized.parts or ".." in normalized.parts:
            raise ValueError("Object-storage keys must be relative and traversal-free.")
        target = self._root.joinpath(*normalized.parts).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("Object-storage key escapes the configured root.") from exc
        return target

    async def put(self, key: str, content: bytes, content_type: str) -> StoredObject:
        target = self._path_for(key)

        def write() -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.tmp")
            temporary.write_bytes(content)
            temporary.replace(target)

        await asyncio.to_thread(write)
        return StoredObject(key=key, content_type=content_type, size=len(content))

    async def get(self, key: str) -> bytes:
        target = self._path_for(key)
        try:
            return await asyncio.to_thread(target.read_bytes)
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(key) from exc

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path_for(key).is_file)

    async def delete(self, key: str) -> None:
        target = self._path_for(key)

        def remove() -> None:
            target.unlink(missing_ok=True)

        await asyncio.to_thread(remove)

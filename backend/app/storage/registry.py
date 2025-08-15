from __future__ import annotations

from app.db.models import CONFIG_ACTIVE_STORAGE_BACKEND, AppConfig
from app.storage.aws import AWSStorageBackend
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend
from sqlalchemy.ext.asyncio import AsyncSession

_REGISTRY: dict[str, type[StorageBackend]] = {}


def register_backend(name: str, cls: type[StorageBackend]) -> None:
    _REGISTRY[name] = cls


def get_backend(name: str) -> StorageBackend:
    try:
        cls = _REGISTRY[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown or unregistered storage backend '{name}'. "
            f"Registered: {sorted(_REGISTRY)}"
        ) from exc
    return cls()


def available_backends() -> list[str]:
    return sorted(_REGISTRY)


async def get_active_backend(session: AsyncSession) -> StorageBackend:
    row = await session.get(AppConfig, CONFIG_ACTIVE_STORAGE_BACKEND)
    if row is None:
        return get_backend("local")
    return get_backend(row.value)


register_backend(LocalStorageBackend.name, LocalStorageBackend)
register_backend(AWSStorageBackend.name, AWSStorageBackend)

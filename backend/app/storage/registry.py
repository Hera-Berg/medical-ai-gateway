"""
Storage backend registry.

The active backend is whatever app_config.active_storage_backend says, read on
every request (per the spec: "read by the FastAPI backend on every request").
This module maps the persisted name -> a concrete StorageBackend instance, and
provides a DB-driven resolver that request handlers use.

Adding a provider = one register_backend() call below. Nothing else changes.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CONFIG_ACTIVE_STORAGE_BACKEND, AppConfig
from app.storage.aws import AWSStorageBackend
from app.storage.base import StorageBackend
from app.storage.local import LocalStorageBackend

# Registered providers. AWSStorageBackend joins here at step 9.
_REGISTRY: dict[str, type[StorageBackend]] = {}


def register_backend(name: str, cls: type[StorageBackend]) -> None:
    _REGISTRY[name] = cls


def get_backend(name: str) -> StorageBackend:
    """Instantiate a backend by name. Raises if unknown/unregistered."""
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
    """
    Resolve the currently-active StorageBackend by reading app_config from the
    DB. Called per request so a switch via the settings UI takes effect
    immediately for subsequent requests, with no app restart.
    """
    row = await session.get(AppConfig, CONFIG_ACTIVE_STORAGE_BACKEND)
    if row is None:
        # Should have been seeded at startup; fall back to local defensively.
        return get_backend("local")
    return get_backend(row.value)


# ── Registration (the one-line-per-provider extension point) ────────────────
register_backend(LocalStorageBackend.name, LocalStorageBackend)
register_backend(AWSStorageBackend.name, AWSStorageBackend)   # step 9

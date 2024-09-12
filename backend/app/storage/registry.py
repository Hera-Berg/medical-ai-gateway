from __future__ import annotations

from app.storage.base import StorageBackend

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

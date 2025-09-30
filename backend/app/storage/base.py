from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class StoredFile:
    locator: str
    backend_name: str
    size_bytes: int


@dataclass
class StorageStats:
    backend_name: str
    total_bytes: int
    disk_usage_percent: float | None
    estimated_monthly_cost_usd: float


@dataclass
class BackendReadiness:
    ready: bool
    detail: str


class StorageBackend(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    async def store_file(
        self, *, data: bytes, filename: str, collection_id: str
    ) -> StoredFile:
        raise NotImplementedError

    @abc.abstractmethod
    async def retrieve_file(self, *, locator: str) -> bytes:
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_file(self, *, locator: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_stats(self) -> StorageStats:
        raise NotImplementedError

    async def check_ready(self) -> "BackendReadiness":
        return BackendReadiness(ready=True, detail="ready")

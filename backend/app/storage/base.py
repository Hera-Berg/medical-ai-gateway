"""
Storage abstraction.

`StorageBackend` is the interface every storage provider implements. Two
concrete backends exist by design:
    • LocalStorageBackend (step 4)  — PDFs on host disk; Qdrant on Docker volumes
    • AWSStorageBackend   (step 9)  — PDFs in S3 (boto3); Qdrant on EBS mounts

Adding a third provider (e.g. GCS) should require ONLY implementing this
interface and registering it — no changes elsewhere. That is the whole point of
the abstraction, and it's what the settings-page dropdown switches between.

At THIS step the methods are stubbed (NotImplementedError) so the interface and
its contract are reviewable before either implementation lands. The signatures
are the contract; later steps fill the bodies.

Note: only PDF *file bytes* go through this interface. Vectors always live in
Qdrant; what changes between backends for Qdrant is the node data DIRECTORY
(local volume vs EBS mount), which is handled at the docker-compose/env level
(QDRANT_NODE_*_VOLUME), not in application code. So this interface is about
(a) where uploaded files are stored and (b) reporting storage stats/cost.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class StoredFile:
    """Result of storing a file: the locator used to retrieve it later."""

    locator: str          # host path (local) or S3 key (aws)
    backend_name: str     # 'local' | 'aws'
    size_bytes: int


@dataclass
class StorageStats:
    """Storage usage + cost, surfaced in the admin panel and dashboard."""

    backend_name: str
    total_bytes: int
    # Local: % of the Docker volume used (for the >80% warning). None for AWS.
    disk_usage_percent: float | None
    # AWS: estimated current storage cost in USD (EBS + S3). 0.0 for Local.
    estimated_monthly_cost_usd: float


@dataclass
class BackendReadiness:
    """Result of a backend readiness probe (shown before switching to it)."""

    ready: bool
    detail: str  # human-readable: why it's ready, or what's missing


class StorageBackend(abc.ABC):
    """Interface for pluggable file storage + storage reporting."""

    #: Short identifier persisted in app_config and on Document rows.
    name: str = "base"

    @abc.abstractmethod
    async def store_file(self, *, data: bytes, filename: str, collection_id: str) -> StoredFile:
        """Persist raw file bytes; return a locator to fetch them later."""
        raise NotImplementedError

    @abc.abstractmethod
    async def retrieve_file(self, *, locator: str) -> bytes:
        """Return the raw bytes for a previously stored file."""
        raise NotImplementedError

    @abc.abstractmethod
    async def delete_file(self, *, locator: str) -> None:
        """Delete a stored file. Idempotent: deleting a missing file is a no-op."""
        raise NotImplementedError

    @abc.abstractmethod
    async def get_stats(self) -> StorageStats:
        """Return current usage + cost for the admin panel / dashboard."""
        raise NotImplementedError

    async def check_ready(self) -> "BackendReadiness":
        """
        Probe whether this backend is usable right now. Default: always ready
        (local disk needs no external config). AWS overrides this to actually
        reach S3, so the settings UI can block switching into a broken state.
        """
        return BackendReadiness(ready=True, detail="ready")

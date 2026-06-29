"""
LocalStorageBackend — stores uploaded file bytes on the host filesystem
(backed by a Docker volume in compose: backend_pdf_data -> /data/pdfs).

Design choices:
  • Files are laid out as  <root>/<collection_id>/<uuid>__<safe_filename>
    - per-collection subdir keeps the tree legible and makes future
      "delete whole collection" cheap (rm the subdir).
    - a UUID prefix prevents collisions when two uploads share a filename,
      without losing the human-readable original name.
  • The LOCATOR we return and persist is the path RELATIVE to the storage root,
    not absolute. That way if the mount path changes (local volume today, a
    different mount tomorrow) existing Document rows still resolve — the root is
    config, the locator is stable.
  • delete_file is idempotent: deleting a missing file is a no-op, per the
    interface contract.
  • get_stats reports disk usage % of the filesystem backing the storage root,
    for the admin panel's >80% warning. Cost is 0.0 (local disk isn't billed
    per-GB).

This is labelled in the UI as "Local Storage — not recommended for large
datasets"; the >80% warning is the teeth behind that label.
"""
from __future__ import annotations

import os
import re
import shutil
import uuid

import anyio

from app.config import get_settings
from app.storage.base import StorageBackend, StoredFile, StorageStats

# Characters we allow through in a stored filename; everything else collapses to
# underscore. Prevents path traversal (no slashes, no ..) and odd shell chars.
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize_filename(filename: str) -> str:
    # Strip any directory components an attacker/user might smuggle in.
    base = os.path.basename(filename)
    cleaned = _SAFE_FILENAME.sub("_", base).strip("._") or "file"
    # Cap length so the full path stays well under filesystem limits.
    return cleaned[:200]


class LocalStorageBackend(StorageBackend):
    name = "local"

    def __init__(self) -> None:
        self._root = get_settings().local_pdf_storage_path

    # ── helpers ─────────────────────────────────────────────────────────────
    def _abs(self, locator: str) -> str:
        """Resolve a relative locator to an absolute path, guarding traversal."""
        root = os.path.abspath(self._root)
        target = os.path.abspath(os.path.join(root, locator))
        # Defense in depth: the resolved path must stay inside root.
        if os.path.commonpath([root, target]) != root:
            raise ValueError(f"Locator escapes storage root: {locator!r}")
        return target

    # ── interface ───────────────────────────────────────────────────────────
    async def store_file(
        self, *, data: bytes, filename: str, collection_id: str
    ) -> StoredFile:
        safe_collection = _sanitize_filename(collection_id)
        safe_name = _sanitize_filename(filename)
        rel_dir = safe_collection
        rel_path = os.path.join(rel_dir, f"{uuid.uuid4().hex}__{safe_name}")
        abs_path = self._abs(rel_path)

        # Create the collection subdir and write bytes off the event loop.
        await anyio.to_thread.run_sync(
            lambda: os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        )
        async with await anyio.open_file(abs_path, "wb") as f:
            await f.write(data)

        return StoredFile(locator=rel_path, backend_name=self.name, size_bytes=len(data))

    async def retrieve_file(self, *, locator: str) -> bytes:
        abs_path = self._abs(locator)
        async with await anyio.open_file(abs_path, "rb") as f:
            return await f.read()

    async def delete_file(self, *, locator: str) -> None:
        abs_path = self._abs(locator)

        def _unlink() -> None:
            try:
                os.remove(abs_path)
            except FileNotFoundError:
                pass  # idempotent per contract

        await anyio.to_thread.run_sync(_unlink)

    async def get_stats(self) -> StorageStats:
        root = os.path.abspath(self._root)

        def _compute() -> StorageStats:
            os.makedirs(root, exist_ok=True)
            # Sum bytes of everything we've stored under root.
            total = 0
            for dirpath, _dirs, files in os.walk(root):
                for name in files:
                    fp = os.path.join(dirpath, name)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
            # Disk usage % of the filesystem backing root (for the >80% warning).
            usage = shutil.disk_usage(root)
            pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
            return StorageStats(
                backend_name=self.name,
                total_bytes=total,
                disk_usage_percent=round(pct, 1),
                estimated_monthly_cost_usd=0.0,  # local disk isn't billed per-GB
            )

        return await anyio.to_thread.run_sync(_compute)

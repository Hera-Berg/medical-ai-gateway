from __future__ import annotations

import os
import re
import shutil
import uuid

import anyio
from app.config import get_settings
from app.storage.base import StorageBackend, StorageStats, StoredFile

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize_filename(filename: str) -> str:
    base = os.path.basename(filename)
    cleaned = _SAFE_FILENAME.sub("_", base).strip("._") or "file"
    return cleaned[:200]


class LocalStorageBackend(StorageBackend):
    name = "local"

    def __init__(self) -> None:
        self._root = get_settings().local_pdf_storage_path

    def _abs(self, locator: str) -> str:
        root = os.path.abspath(self._root)
        target = os.path.abspath(os.path.join(root, locator))
        if os.path.commonpath([root, target]) != root:
            raise ValueError(f"Locator escapes storage root: {locator!r}")
        return target

    async def store_file(
        self, *, data: bytes, filename: str, collection_id: str
    ) -> StoredFile:
        safe_collection = _sanitize_filename(collection_id)
        safe_name = _sanitize_filename(filename)
        rel_dir = safe_collection
        rel_path = os.path.join(rel_dir, f"{uuid.uuid4().hex}__{safe_name}")
        abs_path = self._abs(rel_path)

        await anyio.to_thread.run_sync(
            lambda: os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        )
        async with await anyio.open_file(abs_path, "wb") as f:
            await f.write(data)

        return StoredFile(
            locator=rel_path, backend_name=self.name, size_bytes=len(data)
        )

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
                pass

        await anyio.to_thread.run_sync(_unlink)

    async def get_stats(self) -> StorageStats:
        root = os.path.abspath(self._root)

        def _compute() -> StorageStats:
            os.makedirs(root, exist_ok=True)
            total = 0
            for dirpath, _dirs, files in os.walk(root):
                for name in files:
                    fp = os.path.join(dirpath, name)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
            usage = shutil.disk_usage(root)
            pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
            return StorageStats(
                backend_name=self.name,
                total_bytes=total,
                disk_usage_percent=round(pct, 1),
                estimated_monthly_cost_usd=0.0,
            )

        return await anyio.to_thread.run_sync(_compute)

from __future__ import annotations

import os
import re
import shutil
import uuid

import anyio
from app.config import get_settings
from app.storage.base import StorageBackend, StorageStats, StoredFile

_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


def _sanitize(name: str) -> str:
    base = os.path.basename(name)
    cleaned = _SAFE_FILENAME.sub("_", base).strip("._") or "file"
    return cleaned[:200]


class AWSStorageBackend(StorageBackend):
    name = "aws"

    def __init__(self) -> None:
        s = get_settings()
        self._bucket = s.s3_bucket
        self._region = s.aws_region or None
        self._access_key = s.aws_access_key_id or None
        self._secret_key = s.aws_secret_access_key or None
        self._s3_price = s.aws_s3_price_per_gb_month
        self._ebs_price = s.aws_ebs_price_per_gb_month
        self._ebs_paths = [
            p.strip() for p in s.aws_ebs_mount_paths.split(",") if p.strip()
        ]
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3

            kwargs = {"region_name": self._region} if self._region else {}
            if self._access_key and self._secret_key:
                kwargs["aws_access_key_id"] = self._access_key
                kwargs["aws_secret_access_key"] = self._secret_key
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def _require_bucket(self) -> str:
        if not self._bucket:
            raise ValueError(
                "AWS storage backend selected but S3_BUCKET is not configured."
            )
        return self._bucket

    async def store_file(
        self, *, data: bytes, filename: str, collection_id: str
    ) -> StoredFile:
        bucket = self._require_bucket()
        key = f"{_sanitize(collection_id)}/{uuid.uuid4().hex}__{_sanitize(filename)}"

        def _put() -> None:
            self._get_client().put_object(
                Bucket=bucket, Key=key, Body=data, ContentType="application/pdf"
            )

        await anyio.to_thread.run_sync(_put)
        return StoredFile(locator=key, backend_name=self.name, size_bytes=len(data))

    async def retrieve_file(self, *, locator: str) -> bytes:
        bucket = self._require_bucket()

        def _get() -> bytes:
            resp = self._get_client().get_object(Bucket=bucket, Key=locator)
            return resp["Body"].read()

        return await anyio.to_thread.run_sync(_get)

    async def delete_file(self, *, locator: str) -> None:
        bucket = self._require_bucket()

        def _del() -> None:
            self._get_client().delete_object(Bucket=bucket, Key=locator)

        await anyio.to_thread.run_sync(_del)

    async def get_stats(self) -> StorageStats:
        bucket = self._require_bucket()
        ebs_paths = self._ebs_paths
        s3_price = self._s3_price
        ebs_price = self._ebs_price

        def _compute() -> StorageStats:
            client = self._get_client()
            s3_bytes = 0
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket):
                for obj in page.get("Contents", []):
                    s3_bytes += obj.get("Size", 0)

            ebs_bytes = 0
            for p in ebs_paths:
                try:
                    usage = shutil.disk_usage(p)
                    ebs_bytes += usage.used
                except OSError:
                    pass

            gb = 1024**3
            s3_cost = (s3_bytes / gb) * s3_price
            ebs_cost = (ebs_bytes / gb) * ebs_price
            total_bytes = s3_bytes + ebs_bytes

            return StorageStats(
                backend_name=self.name,
                total_bytes=total_bytes,
                disk_usage_percent=None,
                estimated_monthly_cost_usd=round(s3_cost + ebs_cost, 4),
            )

        return await anyio.to_thread.run_sync(_compute)

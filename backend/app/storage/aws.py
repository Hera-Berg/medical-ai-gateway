"""
AWSStorageBackend — stores uploaded file bytes in S3 (boto3); reports S3 + EBS
storage usage and a per-GB cost estimate for the dashboard.

Symmetry with LocalStorageBackend (deliberate — the interface is the contract):
  • store_file   -> PutObject to s3://{bucket}/{collection_id}/{uuid}__{name}
  • retrieve_file-> GetObject
  • delete_file  -> DeleteObject (idempotent: missing key is a no-op)
  • get_stats    -> S3 prefix size + EBS mount usage, costed via config prices

The LOCATOR is the S3 key (relative to the bucket), mirroring how Local stores a
path relative to its root — so Document.storage_locator means "key within the
active backend's namespace" regardless of backend.

boto3 is synchronous; we run its calls in a worker thread (anyio.to_thread) so
they don't block the async event loop, same pattern as Local's file IO.

WHAT IS / ISN'T VERIFIED: the call sequence and our handling are exercised
against a mocked S3 (moto) in tests. Real S3 behaviour — IAM permissions,
bucket policy, region/network — is only confirmable against a live AWS account
(step 18 provisioning). This backend is NOT the default; nothing routes here
(and nothing bills) unless the active backend is explicitly switched to 'aws'
with credentials present.

Qdrant vectors do NOT flow through here — in AWS mode the Qdrant node data dirs
live on EBS mounts, swapped in purely via QDRANT_NODE_*_VOLUME env vars (no code
change). This backend only governs uploaded FILE bytes (S3) and storage
reporting (S3 + EBS).
"""
from __future__ import annotations

import os
import re
import shutil
import uuid

import anyio

from app.config import get_settings
from app.storage.base import StorageBackend, StoredFile, StorageStats, BackendReadiness

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
        self._client = None  # lazily created on first use

    # ── boto3 client (lazy, thread-confined creation) ───────────────────────
    def _get_client(self):
        if self._client is None:
            import boto3

            # If access keys are blank, boto3 falls back to the default credential
            # chain (instance role, env, ~/.aws) — the recommended prod path.
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

    # ── interface ───────────────────────────────────────────────────────────
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
            # S3 DeleteObject is already idempotent (no error on missing key).
            self._get_client().delete_object(Bucket=bucket, Key=locator)

        await anyio.to_thread.run_sync(_del)

    async def get_stats(self) -> StorageStats:
        bucket = self._require_bucket()
        ebs_paths = self._ebs_paths
        s3_price = self._s3_price
        ebs_price = self._ebs_price

        def _compute() -> StorageStats:
            # S3: sum object sizes in the bucket (paginated).
            client = self._get_client()
            s3_bytes = 0
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket):
                for obj in page.get("Contents", []):
                    s3_bytes += obj.get("Size", 0)

            # EBS: sum used bytes on each configured mount (Qdrant node volumes).
            ebs_bytes = 0
            for p in ebs_paths:
                try:
                    usage = shutil.disk_usage(p)
                    ebs_bytes += usage.used
                except OSError:
                    pass

            gb = 1024 ** 3
            s3_cost = (s3_bytes / gb) * s3_price
            ebs_cost = (ebs_bytes / gb) * ebs_price
            total_bytes = s3_bytes + ebs_bytes

            return StorageStats(
                backend_name=self.name,
                total_bytes=total_bytes,
                disk_usage_percent=None,  # N/A for cloud storage
                estimated_monthly_cost_usd=round(s3_cost + ebs_cost, 4),
            )

        return await anyio.to_thread.run_sync(_compute)

    async def check_ready(self) -> BackendReadiness:
        """
        Probe whether AWS storage is actually usable: bucket configured, and a
        head_bucket call succeeds (confirms the bucket exists AND our credentials
        can reach it — catches wrong bucket/region/keys/permissions, not just
        blank config). Used by the settings UI to block switching into a state
        where the next upload would fail.
        """
        if not self._bucket:
            return BackendReadiness(
                ready=False, detail="S3_BUCKET is not configured."
            )

        def _probe() -> BackendReadiness:
            try:
                self._get_client().head_bucket(Bucket=self._bucket)
                return BackendReadiness(
                    ready=True, detail=f"S3 bucket '{self._bucket}' reachable."
                )
            except Exception as exc:  # botocore ClientError, creds errors, etc.
                # Surface a concise reason without leaking secrets.
                msg = type(exc).__name__
                code = getattr(getattr(exc, "response", None), "get", lambda *_: None)(
                    "Error", {}
                )
                if isinstance(code, dict):
                    msg = code.get("Code", msg)
                return BackendReadiness(
                    ready=False,
                    detail=f"S3 bucket '{self._bucket}' not reachable ({msg}). "
                    "Check credentials, region, and bucket name.",
                )

        return await anyio.to_thread.run_sync(_probe)

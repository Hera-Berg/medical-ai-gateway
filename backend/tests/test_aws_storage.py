"""
Tests for AWSStorageBackend against mocked S3 (moto) — no real AWS, no billing.

Run:  pip install -r requirements-dev.txt && pytest tests/test_aws_storage.py

Proves the call sequence + our handling are correct. Real S3 (IAM, bucket
policy, region/network) is only confirmable against a live account (step 18).
"""
import os

import boto3
import pytest
from moto import mock_aws

BUCKET = "medgw-test-bucket"


@pytest.fixture(autouse=True)
def _aws_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", BUCKET)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    # settings are cached; clear so the test env is picked up
    from app.config import get_settings
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_store_retrieve_delete_roundtrip():
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        from app.storage.aws import AWSStorageBackend

        b = AWSStorageBackend()
        data = b"%PDF-1.4 test " + b"z" * 1000

        sf = await b.store_file(data=data, filename="Doc (v1).pdf", collection_id="c1")
        assert sf.backend_name == "aws"
        assert sf.size_bytes == len(data)
        assert sf.locator.startswith("c1/")

        assert await b.retrieve_file(locator=sf.locator) == data

        stats = await b.get_stats()
        assert stats.total_bytes == len(data)
        assert stats.disk_usage_percent is None

        await b.delete_file(locator=sf.locator)
        assert (await b.get_stats()).total_bytes == 0
        # idempotent
        await b.delete_file(locator=sf.locator)


@pytest.mark.asyncio
async def test_missing_bucket_raises():
    with mock_aws():
        from app.storage.aws import AWSStorageBackend

        b = AWSStorageBackend()
        b._bucket = ""
        with pytest.raises(ValueError):
            await b.store_file(data=b"x", filename="f.pdf", collection_id="c")

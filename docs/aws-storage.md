# AWS S3 storage backend

The gateway stores uploaded PDFs through a pluggable storage backend. The default
is **Local** (a Docker named volume). You can switch to **AWS S3** at runtime
from the Settings page. This doc covers provisioning and tear-down.

## What's stored where

Only the **uploaded PDF bytes** go to the storage backend. Metadata (collections,
documents, chunks) stays in Postgres and vectors stay in Qdrant regardless of
backend. So switching storage affects where source files live, not the index.

## Provision the bucket

`scripts/aws-provision.sh` creates a private, versioned S3 bucket with safe
defaults. Requires the AWS CLI v2, configured (`aws configure`) with permission
to create buckets.

```bash
./scripts/aws-provision.sh --bucket my-medgw-bucket --region ap-southeast-2
```

It creates the bucket, enables versioning, blocks all public access, and tags it
`managed-by=aws-provision.sh` (the teardown script checks this tag). It then
prints the exact `.env` lines to add:

```
AWS_REGION=ap-southeast-2
S3_BUCKET=my-medgw-bucket
AWS_ACCESS_KEY_ID=...        # an IAM principal with s3 access to this bucket
AWS_SECRET_ACCESS_KEY=...
```

## Switch the app to S3

1. Add those vars to `.env` and restart the backend:
   `docker compose up -d --force-recreate backend`.
2. Settings page → switch to **AWS Storage**. The switch is gated on a real
   readiness check (`head_bucket` against your bucket) — it won't let you switch
   if the bucket isn't reachable, and it warns that the index is independent of
   the file store.

## Tear it down (stop billing)

This is the safety net — nothing in this project should silently accrue cloud
cost. `scripts/aws-teardown.sh` empties and deletes the bucket.

```bash
./scripts/aws-teardown.sh --bucket my-medgw-bucket --region ap-southeast-2
```

Safety features:

- Refuses to run without an explicit `--bucket`.
- Verifies the bucket carries the `managed-by=aws-provision.sh` tag (so you can't
  accidentally delete an unrelated bucket); override with `--no-tag-check`.
- Requires you to type the bucket name to confirm (skip with `--yes`).
- Deletes **all object versions and delete markers** (versioning is on, so a
  plain delete would leave billable versions behind), then deletes the bucket.

After teardown, remove the `S3_BUCKET` / `AWS_*` lines from `.env` and switch the
app back to Local storage.

## Cost note

S3 storage cost is tiny for PDFs, but the principle matters: provision
deliberately, tear down when done, and never leave cloud resources running
unattended. The cost dashboard snapshots the storage backend per query so total
platform cost is reconstructable.

#!/usr/bin/env bash
#
# aws-provision.sh — create the AWS resources the AWS storage backend needs.
#
# Scope (deliberately minimal): this provisions the S3 bucket that
# AWSStorageBackend uses for uploaded PDFs. Qdrant-on-EBS is a deployment
# choice documented in docs/aws-storage.md; this script does NOT spin up EC2/EBS
# (that would create ongoing compute charges) — it provisions only the S3 bucket
# so you can flip the storage backend to AWS and see it work.
#
# SAFETY:
#   • Refuses to run without an explicit bucket name.
#   • Enables versioning + blocks public access by default.
#   • Prints exactly what it created so teardown is unambiguous.
#   • Pair with aws-teardown.sh to remove everything and stop charges.
#
# Requirements: awscli v2 configured (aws configure) with permissions to create
# S3 buckets in the target account/region.
#
# Usage:
#   ./scripts/aws-provision.sh --bucket my-medgw-bucket --region ap-southeast-2
#
set -euo pipefail

BUCKET=""
REGION="${AWS_REGION:-ap-southeast-2}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$BUCKET" ]]; then
  echo "ERROR: --bucket is required (e.g. --bucket my-medgw-bucket)" >&2
  exit 2
fi

command -v aws >/dev/null 2>&1 || { echo "ERROR: awscli not found. Install awscli v2." >&2; exit 1; }

echo "→ Account check…"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
echo "  Using AWS account: ${ACCOUNT}, region: ${REGION}"

# S3 CreateBucket: us-east-1 must NOT send a LocationConstraint; all others must.
echo "→ Creating S3 bucket '${BUCKET}'…"
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "  Bucket already exists and is accessible — skipping creation."
else
  if [[ "$REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION"
  fi
  echo "  ✓ created"
fi

echo "→ Enabling versioning…"
aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

echo "→ Blocking public access (private bucket; access via IAM creds only)…"
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "→ Tagging for easy identification + teardown…"
aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging \
  'TagSet=[{Key=project,Value=medical-ai-gateway},{Key=managed-by,Value=aws-provision.sh}]'

cat <<EOF

✓ Provisioned S3 bucket: ${BUCKET}  (region ${REGION})

Next steps:
  1. Put these in your .env:
       AWS_REGION=${REGION}
       S3_BUCKET=${BUCKET}
       AWS_ACCESS_KEY_ID=...        # an IAM user/role with s3 access to this bucket
       AWS_SECRET_ACCESS_KEY=...
  2. Restart the backend so it reads them:  docker compose up -d backend
  3. In the app: Settings → switch to AWS Storage. The readiness check runs a
     real head_bucket against '${BUCKET}' before allowing the switch.

When you're done, tear it ALL down to stop any charges:
  ./scripts/aws-teardown.sh --bucket ${BUCKET} --region ${REGION}
EOF

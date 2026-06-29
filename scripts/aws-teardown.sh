#!/usr/bin/env bash
#
# aws-teardown.sh — remove everything aws-provision.sh created, so AWS stops
# charging you. This is the safety net: nothing in this project should be able
# to silently accrue cloud cost. Run this when you're done demoing on AWS.
#
# What it does:
#   • Deletes ALL objects in the bucket, including ALL versions and delete
#     markers (versioning is enabled by provision, so a plain `rm` is not
#     enough — leftover versions keep the bucket non-empty and still billable).
#   • Deletes the (now empty) bucket itself.
#
# SAFETY:
#   • Requires explicit --bucket.
#   • Verifies the bucket carries the project tag (managed-by=aws-provision.sh)
#     unless you pass --no-tag-check, so you can't accidentally delete an
#     unrelated bucket.
#   • Requires you to type the bucket name to confirm (skip with --yes).
#
# Usage:
#   ./scripts/aws-teardown.sh --bucket my-medgw-bucket --region ap-southeast-2
#   ./scripts/aws-teardown.sh --bucket my-medgw-bucket --yes   # non-interactive
#
set -euo pipefail

BUCKET=""
REGION="${AWS_REGION:-ap-southeast-2}"
ASSUME_YES=0
TAG_CHECK=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --yes) ASSUME_YES=1; shift ;;
    --no-tag-check) TAG_CHECK=0; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$BUCKET" ]]; then
  echo "ERROR: --bucket is required." >&2
  exit 2
fi
command -v aws >/dev/null 2>&1 || { echo "ERROR: awscli not found." >&2; exit 1; }

if ! aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket '${BUCKET}' does not exist or is not accessible. Nothing to do."
  exit 0
fi

# Safety: confirm it's our bucket via the tag provision added.
if [[ "$TAG_CHECK" -eq 1 ]]; then
  echo "→ Verifying bucket is managed by this project…"
  MANAGED="$(aws s3api get-bucket-tagging --bucket "$BUCKET" \
    --query "TagSet[?Key=='managed-by'].Value | [0]" --output text 2>/dev/null || echo "None")"
  if [[ "$MANAGED" != "aws-provision.sh" ]]; then
    echo "REFUSING: bucket '${BUCKET}' is not tagged managed-by=aws-provision.sh" >&2
    echo "(It may not be a bucket this project created. Use --no-tag-check to override.)" >&2
    exit 3
  fi
  echo "  ✓ confirmed (managed-by=aws-provision.sh)"
fi

# Confirmation
if [[ "$ASSUME_YES" -ne 1 ]]; then
  echo
  echo "This will PERMANENTLY DELETE bucket '${BUCKET}' and ALL its contents"
  echo "(every object and every version). This cannot be undone."
  read -r -p "Type the bucket name to confirm: " CONFIRM
  if [[ "$CONFIRM" != "$BUCKET" ]]; then
    echo "Confirmation did not match. Aborting."
    exit 1
  fi
fi

echo "→ Deleting all object versions and delete markers…"
# Page through versions + delete markers and batch-delete them.
while true; do
  PAYLOAD="$(aws s3api list-object-versions --bucket "$BUCKET" --max-items 500 \
    --query '{Objects: (([Versions, DeleteMarkers][] || `[]`)[].{Key:Key,VersionId:VersionId})}' \
    --output json 2>/dev/null || echo '{"Objects": []}')"
  COUNT="$(echo "$PAYLOAD" | python3 -c 'import sys,json;print(len(json.load(sys.stdin).get("Objects") or []))')"
  if [[ "$COUNT" -eq 0 ]]; then
    break
  fi
  echo "$PAYLOAD" | aws s3api delete-objects --bucket "$BUCKET" --delete "file:///dev/stdin" >/dev/null
  echo "  deleted $COUNT object version(s)…"
done

echo "→ Deleting the bucket…"
aws s3api delete-bucket --bucket "$BUCKET" --region "$REGION"

echo
echo "✓ Bucket '${BUCKET}' fully deleted. AWS storage charges for it have stopped."
echo "  Remember to also remove S3_BUCKET / AWS_* from your .env if you're done."

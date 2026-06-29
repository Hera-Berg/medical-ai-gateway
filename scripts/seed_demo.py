#!/usr/bin/env python3
"""
Seed the demo's PERSONAL corpus with a synthetic patient record.

Why this exists: the flagship demo is CROSS-CORPUS comparison — a personal
record against the authoritative guidelines, with provenance shown across the
trust boundary. Out of the box there's only the authoritative corpus, so the
comparison has nothing to compare. This script adds the missing half.

It seeds through the REAL API endpoints (create collection -> upload document),
so it exercises the actual ingestion pipeline (parse -> chunk -> embed -> index)
rather than special-casing data in. If it works, the real upload path works.

Idempotent: if a 'personal' collection named "My Health Record" already exists,
it skips creation (and skips re-upload if the document is already there).

Usage:
    python scripts/seed_demo.py                 # uses http://localhost:8090/api
    BASE_URL=http://localhost:8090/api python scripts/seed_demo.py
    python scripts/seed_demo.py --base http://localhost:8090/api
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

COLLECTION_NAME = "My Health Record"
SOURCE_LABEL = "Synthetic patient summary (demo)"
GEN_SCRIPT = Path(__file__).parent / "generate_synthetic_record.py"


def _base_url(cli_base: str | None) -> str:
    return (cli_base or os.getenv("BASE_URL") or "http://localhost:8090/api").rstrip("/")


def _find_personal_collection(client: httpx.Client, base: str) -> dict | None:
    r = client.get(f"{base}/collections")
    r.raise_for_status()
    for c in r.json():
        if c.get("name") == COLLECTION_NAME and c.get("corpus_type") == "personal":
            return c
    return None


def _collection_has_docs(client: httpx.Client, base: str, collection_id: str) -> bool:
    r = client.get(f"{base}/documents", params={"collection_id": collection_id})
    if r.status_code != 200:
        return False
    return len(r.json()) > 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="API base URL (default http://localhost:8090/api)")
    ap.add_argument("--force", action="store_true", help="re-upload even if a doc exists")
    args = ap.parse_args()
    base = _base_url(args.base)

    print(f"→ Seeding demo personal corpus via {base}")

    # 1. generate the synthetic PDF into a temp file
    tmp = Path(tempfile.mkdtemp()) / "synthetic_patient_summary.pdf"
    print("→ Generating synthetic patient record PDF…")
    res = subprocess.run(
        [sys.executable, str(GEN_SCRIPT), str(tmp)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print("✗ Failed to generate PDF:\n", res.stderr)
        return 1
    print(f"  ✓ {tmp.name} ({tmp.stat().st_size} bytes)")

    with httpx.Client(timeout=120.0) as client:
        # sanity: API reachable?
        try:
            client.get(f"{base}/collections").raise_for_status()
        except Exception as e:
            print(f"✗ API not reachable at {base} ({e}).")
            print("  Is the stack up?  docker compose up -d")
            return 1

        # 2. create (or find) the personal collection
        existing = _find_personal_collection(client, base)
        if existing:
            print(f"→ Personal collection '{COLLECTION_NAME}' already exists "
                  f"(id {existing['id'][:8]}…) — reusing.")
            collection = existing
            if _collection_has_docs(client, base, existing["id"]) and not args.force:
                print("✓ It already contains a document. Nothing to do. "
                      "(use --force to re-upload)")
                return 0
        else:
            print(f"→ Creating personal collection '{COLLECTION_NAME}'…")
            r = client.post(
                f"{base}/collections",
                json={
                    "name": COLLECTION_NAME,
                    "corpus_type": "personal",
                    "description": "Synthetic personal health record for the cross-corpus demo.",
                },
            )
            r.raise_for_status()
            collection = r.json()
            print(f"  ✓ created (id {collection['id'][:8]}…)")

        # 3. upload the PDF through the real ingestion pipeline
        print("→ Uploading synthetic record (parse → chunk → embed → index)…")
        with open(tmp, "rb") as fh:
            r = client.post(
                f"{base}/documents",
                data={
                    "collection_id": collection["id"],
                    "source_version": SOURCE_LABEL,
                },
                files={"file": ("synthetic_patient_summary.pdf", fh, "application/pdf")},
            )
        if r.status_code != 200:
            print(f"✗ Upload failed ({r.status_code}): {r.text[:300]}")
            return 1
        doc = r.json()
        print(f"  ✓ ingested: {doc.get('chunk_count', '?')} chunks indexed")

    print()
    print("✓ Demo personal corpus seeded.")
    print("  Try a cross-corpus question in Chat, e.g.:")
    print('    "How does my most recent HbA1c compare to the guideline target?"')
    print("  You should see BOTH a personal chunk and an authoritative chunk,")
    print("  each with its own corpus badge, in the thinking-transparency panel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

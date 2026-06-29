#!/usr/bin/env python3
"""
verify_sharding.py — confirm the Qdrant cluster shards and replicates data
across both nodes (spec step 6: "confirm documents shard correctly across both
nodes before proceeding").

This turns the raw /cluster JSON into a human-readable report of:
  • how many shards a collection has,
  • how points are distributed across shards,
  • whether each shard is replicated onto the other peer (replication_factor),
  • the health state of every shard replica.

Usage (from the host, talking to the cluster over the Docker network):

    # against every collection:
    docker run --rm --network medical-ai-gateway_default \
        -v "$PWD/scripts:/s" python:3.11-slim \
        python /s/verify_sharding.py

    # or one collection:
    ... python /s/verify_sharding.py <collection_name>

It uses only the stdlib (urllib) so it needs no pip install inside the
throwaway container.

HONEST NOTE printed in the report: two nodes on one host demonstrates the
sharding + replication *configuration*; it is NOT fault tolerance, because both
replicas share the machine. Real durability requires nodes on separate hosts.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

NODE1 = os.environ.get("QDRANT_NODE_1_URL", "http://qdrant-node1:6333")


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{NODE1}{path}", timeout=10) as r:
        return json.loads(r.read())


def list_collections() -> list[str]:
    data = _get("/collections")
    return [c["name"] for c in data["result"]["collections"]]


def peers() -> dict[int, str]:
    """peer_id -> uri, from the cluster topology."""
    data = _get("/cluster")
    out = {}
    for pid, info in data["result"]["peers"].items():
        out[int(pid)] = info["uri"]
    return out


def report_collection(name: str, peer_uris: dict[int, str]) -> bool:
    data = _get(f"/collections/{name}/cluster")
    r = data["result"]
    this_peer = r["peer_id"]
    local = r.get("local_shards", [])
    remote = r.get("remote_shards", [])
    transfers = r.get("shard_transfers", [])

    print(f"\n=== {name} ===")
    print(f"  queried peer : {this_peer} ({peer_uris.get(this_peer, '?')})")
    print(f"  shard_count  : {r.get('shard_count')}")

    # Build shard_id -> set of peers holding it.
    holders: dict[int, set[int]] = {}
    points: dict[int, int] = {}
    for s in local:
        holders.setdefault(s["shard_id"], set()).add(this_peer)
        points[s["shard_id"]] = s.get("points_count", 0)
    for s in remote:
        holders.setdefault(s["shard_id"], set()).add(s["peer_id"])

    total_points = sum(points.values())
    print(f"  local points : {total_points} (across {len(points)} local shards)")

    all_replicated = True
    distinct_peers: set[int] = set()
    for shard_id in sorted(holders):
        ph = sorted(holders[shard_id])
        distinct_peers.update(ph)
        replicas = len(ph)
        if replicas < 2:
            all_replicated = False
        pc = points.get(shard_id)
        pc_str = f"{pc} pts (local)" if pc is not None else "remote-only here"
        print(f"    shard {shard_id}: {pc_str}, replicas on peers {ph}")

    sharded = (r.get("shard_count", 0) or 0) >= 2
    multi_node = len(distinct_peers) >= 2

    print(f"  -> sharded across >=2 shards : {'YES' if sharded else 'no'}")
    print(f"  -> spread across >=2 peers   : {'YES' if multi_node else 'no'}")
    print(f"  -> every shard replicated    : {'YES' if all_replicated else 'no'}")
    if transfers:
        print(f"  -> shard transfers in flight : {len(transfers)} (rebalancing)")

    return sharded and multi_node and all_replicated


def main() -> int:
    try:
        peer_uris = peers()
    except Exception as exc:
        print(f"ERROR: cannot reach cluster at {NODE1}: {exc}")
        return 2

    print(f"Cluster peers ({len(peer_uris)}):")
    for pid, uri in peer_uris.items():
        print(f"  {pid}  {uri}")

    targets = sys.argv[1:] or list_collections()
    if not targets:
        print("\nNo collections yet — upload a document first.")
        return 0

    ok = True
    for name in targets:
        try:
            ok = report_collection(name, peer_uris) and ok
        except Exception as exc:
            print(f"\n=== {name} ===\n  ERROR: {exc}")
            ok = False

    print("\n" + "-" * 64)
    print("HONEST CAVEAT: two nodes on one host proves the sharding + replication")
    print("CONFIGURATION and lets you watch distribution — it is NOT fault")
    print("tolerance, since both replicas share the machine. Real durability")
    print("needs nodes on separate hosts (see docs/scaling.md).")
    print("-" * 64)

    print(f"\nRESULT: {'ALL CHECKS PASSED' if ok else 'some checks did not pass'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

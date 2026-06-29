# Scaling

How the gateway scales horizontally — and where it deliberately doesn't.

## The stateless backend

The FastAPI backend holds no per-request state in memory: every request reads
what it needs from Postgres and Qdrant. That makes it horizontally scalable —
run N copies and any of them can serve any request.

```bash
docker compose up -d --scale backend=3
```

This starts three backend replicas. Concurrent startup is safe: the entrypoint
runs Alembic migrations under a **Postgres advisory lock**, so three replicas
booting at once won't race on the schema.

## The load balancer

nginx is the sole ingress and round-robins across the replicas. The detail that
makes it actually work: nginx resolves upstream DNS **once at startup** by
default, which would pin it to a single replica's IP. Instead the config points
nginx at Docker's embedded DNS resolver (`127.0.0.11`) and uses a *variable* in
`proxy_pass`, forcing per-request re-resolution. Docker's DNS returns all
replica IPs in rotation → genuine round-robin, and replicas added/removed at
runtime are picked up within the `valid=10s` window.

### See it working

```bash
for i in $(seq 1 6); do curl -s http://localhost:8090/api/admin/whoami; echo; done
```

`/api/admin/whoami` returns the serving container's hostname + PID. Across
repeated calls the hostname rotates through the replicas. Scale back to
`--scale backend=1` and it stays constant — the contrast proves the balancing.
(Just after scaling, the 10s DNS window means it can take a few seconds for all
replicas to appear.)

## The deliberate bottleneck: Postgres

A **single** Postgres instance backs the whole stack. This is intentional and
documented rather than hidden: the stateless backend scales out, but every
replica talks to the one database, so Postgres is the ceiling. Scaling it
further (read replicas, connection pooling like PgBouncer, partitioning) is the
obvious next step and is called out on the Admin page in-app.

## The vector tier

Qdrant runs as a 2-node cluster with `shard_number=2, replication_factor=2`:
data is split into 2 shards, each replicated twice, so both nodes hold a full
copy. The Admin page shows the live shard placement.

**Honest caveat:** both nodes are containers on **one host**. This demonstrates
distributed sharding/replication *configuration* and lets you reason about
placement, but it is **not** fault tolerance — losing the host loses both nodes.
Real HA would put the nodes on separate physical machines.

## Inference

Inference scales independently on RunPod Serverless — each model is its own
auto-scaling endpoint with scale-to-zero. Backend replicas are stateless callers
of those endpoints, so the app tier and the GPU tier scale separately.

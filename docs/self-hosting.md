# Self-hosting guide

Everything needed to run the Medical AI Gateway on your own machine.

## Requirements

- Docker + Docker Compose (v2).
- ~4 GB RAM free for the stack (Postgres + 2 Qdrant nodes + backend + frontend).
- Outbound internet for the build (pulls base images, npm/pip packages, the
  FastEmbed model, and Google Fonts at build time).
- Optional, only for going live: a RunPod account (real inference), a
  Cloudflare-managed domain (public URL), an AWS account (S3 storage).

## First run

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8090`. The stack is fully functional offline-of-RunPod in
**mock mode** — real retrieval and cost accounting, simulated answer text, $0.

## Environment variables

All live in `.env` (copied from `.env.example`). Key ones:

| Variable                  | Purpose                                                        |
| ------------------------- | ------------------------------------------------------------- |
| `POSTGRES_USER/PASSWORD/DB` | Postgres credentials. Change the password for any real use.  |
| `MOCK_INFERENCE`          | `1` = simulated answers, $0. `0` = real RunPod inference.      |
| `RUNPOD_API_KEY`          | RunPod key (write scope). Needed when `MOCK_INFERENCE=0`.      |
| `RUNPOD_API_STYLE`        | `openai` (default) or `native`. See runpod-deploy.md.         |
| `CLOUDFLARE_TUNNEL_TOKEN` | Tunnel token. Blank = local-only on `:8090`.                  |
| `AWS_ACCESS_KEY_ID` etc.  | Only for S3 storage mode. See aws-storage.md.                 |
| `SUBSCRIPTION_COMPARISON_USD_MONTH` | Break-even anchor (default 20).                     |

Per-model RunPod endpoint IDs live in `backend/app/inference/models.yaml`, not
`.env`.

## Common operations

```bash
# logs
docker compose logs -f backend

# rebuild after editing code or .env (always use --build --force-recreate)
docker compose up -d --build --force-recreate backend

# scale the backend (see docs/scaling.md)
docker compose up -d --scale backend=3

# run with the public tunnel (see docs/cloudflare-tunnel.md)
docker compose --profile tunnel up -d

# stop everything
docker compose down

# stop and wipe data (Postgres + Qdrant volumes)
docker compose down -v
```

## Data & persistence

- **Postgres** holds collections, documents, chunks, queries, costs, and trace
  events. Backed by a Docker named volume.
- **Qdrant** (2 nodes) holds the vector embeddings, sharded + replicated. Each
  node has its own volume.
- Uploaded PDFs are stored by the active **storage backend** (Local volume by
  default, or S3). The PDF bytes live there; the metadata + vectors live in
  Postgres/Qdrant.

`docker compose down` keeps volumes; `down -v` deletes them. If you reset Qdrant
you must re-ingest documents (the vectors are gone); the Settings page warns
about a fresh index when switching storage.

## Gotchas

- **Editing `.env` or YAML needs a rebuild.** A running container keeps its old
  values until `docker compose up -d --build --force-recreate <service>`.
- **Values hardcoded in `docker-compose.yml` override `.env`.** If a variable
  won't change, check the compose `environment:` block.
- **First backend boot runs DB migrations** under a Postgres advisory lock, so
  multiple replicas starting together is safe (they don't race).

# Medical AI Gateway

> **Demo & educational tool. Not medical advice. Not a diagnostic device.**
> All personal health records in this project are **synthetic**. It is a
> portfolio piece, not a clinical product.

A self-hostable, **cost-transparent** medical RAG platform. Upload published
clinical guidelines (the *authoritative* corpus), compare a *synthetic* personal
health record against them, and see every retrieved passage's provenance across
the trust boundary between the two. You choose the model and the *thinking depth*
per query; the dashboard logs the **real per-second GPU cost** of each query and
shows where self-hosting crosses a subscription price line.

🔗 **Live demo:** `https://medical.your-domain.com` (gated by Cloudflare Access)

---

## Why this project exists

Most RAG demos hide three things: what retrieval actually returned, what it
costs, and where the data came from. This project makes all three first-class:

- **Cost transparency.** Inference runs on RunPod Serverless, billed per
  GPU-second. Every query records its true cost (cold-start delay + execution
  time × per-second rate). A break-even widget shows, from *measured* spend, how
  many queries per month it takes before self-hosting beats a flat subscription.
- **Provenance across a trust boundary.** Two corpora — `authoritative`
  (published literature) and `personal` (the user's own synthetic records) — are
  kept visually and structurally distinct. The flagship interaction is a
  cross-corpus question ("how does my last HbA1c compare to the guideline
  target?") that surfaces chunks from *both*, each badged with its source.
- **Honest mechanics.** "Thinking depth" is depth, not guaranteed accuracy —
  Low/Medium/High run 1/3/6 real inference passes, and the per-pass trace is
  inspectable. Retrieved chunks say "Retrieved from X · NN%", never "Verified."

## What it demonstrates (engineering)

- **Distributed vector store** — a 2-node Qdrant cluster with sharding +
  replication (`shard_number=2, replication_factor=2`), with an honest caveat
  that two nodes on one host is a *topology* demo, not real fault tolerance.
- **Horizontal scaling** — a stateless FastAPI backend behind an nginx load
  balancer that round-robins across replicas via per-request DNS re-resolution.
  The single Postgres instance is a *deliberately documented* bottleneck.
- **Pluggable storage** — Local (Docker volumes) or AWS S3, switchable at
  runtime, with provision/teardown scripts so cloud cost can't silently accrue.
- **Real LLM serving** — multiple open models on RunPod Serverless via an
  OpenAI-compatible client, with scale-to-zero, time-based cost accounting, and a
  mock mode for $0 development.
- **Edge-enforced access** — no auth in the app by design; Cloudflare Access
  gates the public hostname, demonstrating defense-in-depth where auth belongs
  for a stateless service.

## Architecture

Seven services via one `docker compose up`:

```
              Cloudflare edge (TLS + Access gate)
                          |  tunnel (outbound-only)
                          v
   cloudflared --> nginx (sole ingress, load balancer)
                    |            |
                    v            v
            Next.js frontend   FastAPI backend xN (stateless)
                                 |        |         |
                                 v        v         v
                           Postgres   Qdrant x2  RunPod Serverless
                          (metadata,  (vectors,   (LLM inference,
                           a noted     sharded +   per-second billed)
                           bottleneck) replicated)
```

Full detail in [`docs/architecture.md`](docs/architecture.md).

## Quickstart

```bash
git clone <your-repo-url> medical-ai-gateway
cd medical-ai-gateway
cp .env.example .env          # defaults run fully local, in mock mode
docker compose up -d --build
```

Open `http://localhost:8090`. With the defaults you get the full app — real
retrieval, provenance, trace, and cost — with *simulated* answer text and **$0
spend** (`MOCK_INFERENCE=1`). To seed the cross-corpus demo:

```bash
pip install httpx reportlab
python scripts/seed_demo.py    # adds a synthetic personal health record
```

Then ask, in Chat: *"How does my most recent HbA1c compare to the guideline
target?"* — and watch chunks from both corpora appear with source badges.

## Going live

- **Real inference** -> [`docs/runpod-deploy.md`](docs/runpod-deploy.md): deploy a
  model on RunPod, wire its endpoint, set `MOCK_INFERENCE=0`.
- **Public URL** -> [`docs/cloudflare-tunnel.md`](docs/cloudflare-tunnel.md): a
  Cloudflare Tunnel + Access, no open inbound ports.
- **Scaling** -> [`docs/scaling.md`](docs/scaling.md): `--scale backend=N` and how
  the load balancer distributes across replicas.
- **AWS storage** -> [`docs/aws-storage.md`](docs/aws-storage.md): switch to S3,
  with provision/teardown scripts.
- **Self-hosting** -> [`docs/self-hosting.md`](docs/self-hosting.md): full
  environment reference.

## Honesty & limitations

This project is deliberate about what it is *not*:

- Personal records are **synthetic** and stamped as such; the app never presents
  output as medical advice.
- The 2-node Qdrant cluster shares one host — it proves sharding/replication
  *configuration*, not physical fault tolerance.
- A single Postgres instance is the scaling bottleneck (named, not hidden).
- "Thinking depth" buys thoroughness and more retrieval, not guaranteed
  correctness — the per-pass trace lets you judge for yourself.
- Mock-mode costs are *modelled* (no GPU billed) and are clearly labelled as
  such in the UI so they're never mistaken for real spend.

## Tech stack

Next.js 14 · FastAPI · PostgreSQL · Qdrant · FastEmbed (BGE-small) · pypdfium2 ·
Docker Compose · nginx · Cloudflare Tunnel + Access · RunPod Serverless (vLLM) ·
boto3 / S3.

## License & data

Code is provided as a portfolio sample. The bundled clinical guideline is used
for demonstration; personal records are synthetic and generated by
`scripts/generate_synthetic_record.py`. Not for clinical use.

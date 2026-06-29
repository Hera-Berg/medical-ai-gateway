# Medical AI Gateway — System Architecture

> **Demo & educational tool. Not medical advice. Not a diagnostic device.**
> This project compares synthetic personal health records against published
> clinical literature to demonstrate RAG provenance across a trust boundary.
> It is a portfolio piece, not a clinical product.

---

## 1. High-level positioning

This is a **cost-transparent, data-sovereign, domain-specialised** RAG platform.
It is *not* marketed as "cheaper than ChatGPT" — instead the dashboard measures
your actual per-query spend against a $20/mo subscription line and shows you the
**break-even point**, which is a stronger and more honest result.

Two corpora live side by side and are *never merged*:

| Corpus type     | Source                                   | Lifecycle              | Write access (by design) |
|-----------------|------------------------------------------|------------------------|--------------------------|
| `authoritative` | PubMed abstracts, NICE NG28, WHO/NHS PDFs | Curated, persistent, seeded | Admin-only *(enforcement is a documented extension point — there is no auth layer yet)* |
| `personal`      | The user's own (synthetic) health records | Ephemeral, user-supplied via drag-and-drop | Anyone |

The entire value proposition is **cross-corpus comparison**: retrieve from both,
label every chunk's provenance (which corpus, which document, which page, which
*version* of the guideline), and let a human verify. Chunk cards say
**"Retrieved from [source] · NN%"**, never "Verified" — retrieval proves semantic
proximity, not clinical support.

---

## 2. System architecture (logical)

```
                          ┌─────────────────────────────────────────┐
                          │            PUBLIC INTERNET                │
                          │   user's browser  →  https://your.domain  │
                          └───────────────────┬───────────────────────┘
                                              │  (TLS terminated at Cloudflare edge)
                                              │  Optional: Cloudflare Access (SSO/password)
                                              │  can be layered here later — NO app code change
                                              ▼
                          ┌─────────────────────────────────────────┐
                          │        CLOUDFLARE EDGE NETWORK            │
                          └───────────────────┬───────────────────────┘
                                              │  encrypted tunnel (outbound only)
                                              │  ZERO inbound ports open on host
                                              ▼
  ╔═══════════════════════════════════════════════════════════════════════════════╗
  ║                          SINGLE HOST  (docker-compose)                          ║
  ║                                                                                 ║
  ║   ┌──────────────┐                                                              ║
  ║   │  cloudflared │  (Docker service; token via CLOUDFLARE_TUNNEL_TOKEN)         ║
  ║   │   tunnel     │                                                              ║
  ║   └──────┬───────┘                                                              ║
  ║          │ proxies to → nginx:80   (internal Docker network only)               ║
  ║          ▼                                                                      ║
  ║   ┌──────────────────────────────────────────────────────────────────────┐     ║
  ║   │                            NGINX  (reverse proxy)                       │     ║
  ║   │   / and /_next/*        → frontend:3000   (Next.js)                     │     ║
  ║   │   /api/*                → backend  (round-robin LB across replicas)     │     ║
  ║   │   upstream backend { server backend:8000; }  ← scale = more servers     │     ║
  ║   └──────┬───────────────────────────────────────────────┬─────────────────┘     ║
  ║          │                                                │                      ║
  ║          ▼                                                ▼                      ║
  ║   ┌──────────────┐                          ┌──────────────────────────────┐    ║
  ║   │  FRONTEND     │                          │  BACKEND  (FastAPI, x N)       │    ║
  ║   │  Next.js 14   │                          │  STATELESS — scale via         │    ║
  ║   │  App Router   │                          │  deploy.replicas in compose    │    ║
  ║   │  Tailwind +   │                          │                                │    ║
  ║   │  shadcn/ui    │                          │  ┌──────────────────────────┐  │    ║
  ║   │               │                          │  │ StorageBackend (ABC)      │  │    ║
  ║   │  Pages:       │                          │  │  ├ LocalStorageBackend    │  │    ║
  ║   │  • Chat       │                          │  │  └ AWSStorageBackend(boto3)│ │    ║
  ║   │  • KnowledgeB │                          │  └──────────────────────────┘  │    ║
  ║   │  • RAG Inspect│                          │  ┌──────────────────────────┐  │    ║
  ║   │  • Dashboard  │                          │  │ RAG pipeline (LangChain)  │  │    ║
  ║   │  • Settings   │                          │  │  FileHandler (ABC)         │  │    ║
  ║   │  • Admin      │                          │  │   └ PdfFileHandler         │  │    ║
  ║   └──────────────┘                          │  │  → chunk → embed           │  │    ║
  ║                                              │  │  (sentence-transformers)   │  │    ║
  ║                                              │  └──────────────────────────┘  │    ║
  ║                                              │  ┌──────────────────────────┐  │    ║
  ║                                              │  │ Inference orchestrator     │  │    ║
  ║                                              │  │  Low / Medium / High tiers │  │    ║
  ║                                              │  │  → RunPod Serverless API   │  │    ║
  ║                                              │  │  emits ordered trace_events│  │    ║
  ║                                              │  └──────────────────────────┘  │    ║
  ║                                              └──┬──────────┬──────────┬────────┘    ║
  ║                                                 │          │          │             ║
  ║                  ┌──────────────────────────────┘          │          └──────────┐  ║
  ║                  ▼                                          ▼                     ▼  ║
  ║   ┌──────────────────────────────┐      ┌──────────────────────┐   ┌────────────────┐
  ║   │   QDRANT  (distributed)        │      │   POSTGRESQL          │   │  external:     │
  ║   │   ┌────────────┐ ┌───────────┐ │      │   • documents          │   │  RunPod        │
  ║   │   │ qdrant-node1│ │qdrant-node2││      │   • chunks (metadata)  │   │  Serverless    │
  ║   │   │  shard A,B  │ │ shard A,B  ││      │   • queries / costs    │   │  GPU endpoints │
  ║   │   │  replica    │ │ replica    ││      │   • collections        │   │  (per model)   │
  ║   │   └─────┬──────┘ └─────┬──────┘│      │   • app_config         │   └────────────────┘
  ║   │         │  raft/gossip  │       │      │     (active_backend…)  │                     ║
  ║   │  replication_factor = 2 │       │      │   SINGLE INSTANCE =    │                     ║
  ║   │  shard_number = 2       │       │      │   scaling bottleneck   │                     ║
  ║   │   vol: QDRANT_NODE_1/2_VOLUME   │      │   (see scaling.md)     │                     ║
  ║   │   (local Docker vol OR EBS mnt) │      └──────────────────────┘                     ║
  ║   └──────────────────────────────┘                                                      ║
  ║                                                                                          ║
  ║   PDF bytes: LocalStorageBackend → host disk volume                                      ║
  ║             AWSStorageBackend   → S3 (boto3)                                              ║
  ╚══════════════════════════════════════════════════════════════════════════════════════╝
```

### Honest notes on the topology (these go in scaling.md too)

- **Two Qdrant nodes on one host is a *topology demo*, not real fault tolerance.**
  Both nodes share the same physical machine and (in Local mode) the same disk.
  `replication_factor=2` and `shard_number=2` demonstrate the *configuration* and
  let you observe shard distribution via the API, but a single-host failure takes
  down both replicas. Real fault tolerance requires nodes on separate machines.
  This is stated plainly in the admin panel and docs — claiming otherwise would be
  the kind of thing an interviewer catches immediately.
- **PostgreSQL is a single instance and is the documented scaling bottleneck.**
  Production path (managed RDS, read replicas) is in `docs/scaling.md`.
- **The backend is the only horizontally-scalable compute tier** (stateless,
  round-robined by Nginx). State lives entirely in Postgres + Qdrant + S3.

---

## 3. Request flow: a cross-corpus query (the core use case)

```
1. User on Chat page: selects model (e.g. Mistral 7B), thinking tier (e.g. Medium),
   and collection scope (authoritative=NICE+PubMed, personal=my synthetic record).
   Types: "Given my last labs, am I meeting the diabetes guideline targets?"

2. POST /api/query  →  Nginx  →  backend replica (round-robin)

3. Backend reads app_config.active_storage_backend from Postgres.
   Instantiates the matching StorageBackend.

4. Inference orchestrator runs the tier:
   ── Medium = 3 real RunPod calls, each emitting trace_events ──
   • PASS 1 (propose):    embed query → retrieve top-k from BOTH corpora
                          → RunPod call → intermediate answer
   • PASS 2 (challenge):  re-retrieve against a devil's-advocate prompt
                          → RunPod call → critique citing contradicting chunks
   • PASS 3 (reconcile):  retrieve once more → RunPod call → final synthesis
   Every retrieval and every pass is appended to an ORDERED trace_events[] array.

5. Each query logs to Postgres: model, tier, n_calls, tokens/call, USD cost,
   latency/call + total. If AWS backend active, also current EBS+S3 storage cost.

6. Response returns: { answer, trace_events[], cost_breakdown }.
   Frontend renders the answer + a collapsible timeline of mini-headings:
     ▸ [retrieval] Retrieved 5 chunks  (click → chunk cards w/ provenance + version)
     ▸ [pass:propose] Initial answer    (click → prompt + intermediate output)
     ▸ [retrieval] Re-retrieved 4 chunks
     ▸ [pass:challenge] Model challenging its own answer
     ▸ [retrieval] ...
     ▸ [pass:reconcile] Final synthesis
   Chunk cards: model-generated text in one colour; retrieved evidence in another.
   Each card: exact text · source doc · page/section · guideline version · NN% sim.
```

---

## 4. Key abstractions (extension points)

| Abstraction        | Base class         | Concrete impls now      | To add a new one                    |
|--------------------|--------------------|-------------------------|-------------------------------------|
| Storage backend    | `StorageBackend`   | `Local`, `AWS`          | implement the ABC, register it      |
| File ingestion     | `FileHandler`      | `PdfFileHandler`        | implement the ABC, register by ext  |
| Inference tier     | `ThinkingTier`     | `Low`, `Medium`, `High` | add a tier descriptor (pass list)   |
| Model → GPU tier   | `models.yaml` config | Mistral7B, Llama3-8B, Llama3-70B | add a config entry        |

No new provider/parser/model should require touching unrelated code — each is a
registry + interface.

---

## 5. Thinking tiers — framed honestly

Tiers are a **depth / thoroughness** dial, not a guaranteed-quality dial. More
passes = more retrieval, more scrutiny, more citations. Whether that *improves
the answer* is conditional (self-critique helps catch evidence-checkable errors;
it can also launder a confident wrong answer). The multi-pass machinery is
instrumented (trace_events + per-pass logging) precisely so you can run an
evaluation and find out *when* extra passes help — which is the honest,
research-credible framing.

| Tier   | Passes | Structure                                            | Cost mult (base, indicative) |
|--------|--------|------------------------------------------------------|------------------------------|
| Low    | 1      | retrieve → answer                                    | 1×                           |
| Medium | 3      | propose → devil's-advocate → reconcile (each w/ RAG) | ~3×                          |
| High   | 6      | propose → multi-retrieval/fact-check → adversarial self-critique → cited synthesis | ~6× |

> Cost multipliers are *indicative* and shown pre-submit as an estimate; the
> dashboard logs the *actual* token-based cost after the run, because true cost
> can't be known before generation.

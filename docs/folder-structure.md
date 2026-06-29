# Medical AI Gateway — Repository Structure

Monorepo. Each docker-compose service maps to its own top-level folder where it
has real source; infra/config-only services (nginx, cloudflared, qdrant) live
under `infra/`. Annotations marked **[scaffold]** are created in the current
step; everything else is stubbed or filled in later build steps (the number in
parentheses is the build-order step from the spec).

```
medical-ai-gateway/
│
├── docker-compose.yml              # [scaffold] all 7 services wired together
├── .env.example                    # [scaffold] every env var documented
├── .gitignore                      # [scaffold]
├── README.md                       # [scaffold] quickstart + scaling section
│
├── frontend/                       # Next.js 14 App Router (step 14)
│   ├── Dockerfile                  # [scaffold] (multi-stage; runnable empty app)
│   ├── package.json                # [scaffold]
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── app/
│   │   ├── layout.tsx              # persistent "not medical advice" banner lives here
│   │   ├── page.tsx                # Chat UI (model/tier/collection selectors)
│   │   ├── knowledge-base/page.tsx # upload, chunking progress, library, collections (7)
│   │   ├── rag-inspector/page.tsx  # chunk browser, embedding viewer, dry-run, UMAP (8)
│   │   ├── dashboard/page.tsx      # cost + break-even widget (13)
│   │   ├── settings/page.tsx       # storage backend selector + confirm (10)
│   │   └── admin/page.tsx          # Qdrant + Postgres stats (15)
│   ├── components/
│   │   ├── ui/                     # shadcn/ui generated components
│   │   ├── thinking-panel/         # collapsible trace timeline + chunk cards
│   │   ├── chunk-card.tsx          # "Retrieved from [source] · NN%" + provenance
│   │   ├── disclaimer-banner.tsx   # structural, persistent
│   │   └── cost/                   # dashboard + break-even widgets
│   └── lib/
│       └── api.ts                  # typed client for FastAPI (trace_events model)
│
├── backend/                        # FastAPI, Python 3.11 (steps 2,3,5,11,12,13)
│   ├── Dockerfile                  # [scaffold] (runnable; /health works)
│   ├── pyproject.toml              # [scaffold] deps pinned
│   ├── requirements.txt            # [scaffold]
│   ├── app/
│   │   ├── main.py                 # [scaffold] FastAPI app + /health
│   │   ├── config.py               # [scaffold] settings from env
│   │   ├── db/
│   │   │   ├── session.py          # SQLAlchemy engine/session (3)
│   │   │   ├── models.py           # documents, chunks, queries, costs, collections, app_config (3)
│   │   │   └── migrations/         # alembic (3)
│   │   ├── storage/
│   │   │   ├── base.py             # StorageBackend ABC (2)
│   │   │   ├── local.py            # LocalStorageBackend (4)
│   │   │   ├── aws.py              # AWSStorageBackend (boto3) (9)
│   │   │   └── registry.py         # backend selection from app_config
│   │   ├── ingestion/
│   │   │   ├── handlers/
│   │   │   │   ├── base.py         # FileHandler ABC — the extension point (5)
│   │   │   │   └── pdf.py          # PdfFileHandler (5)
│   │   │   ├── chunker.py          # (5)
│   │   │   └── embedder.py         # sentence-transformers (5)
│   │   ├── rag/
│   │   │   ├── qdrant_client.py    # collection=namespace, shard/replica config (5,6)
│   │   │   ├── retriever.py        # cross-corpus retrieval + scoring (5)
│   │   │   └── reducer.py          # UMAP/PCA → 2D for inspector (8)
│   │   ├── inference/
│   │   │   ├── runpod_client.py    # per-model endpoint calls (11)
│   │   │   ├── tiers.py            # ThinkingTier defs: Low/Medium/High (12)
│   │   │   └── orchestrator.py     # runs passes, emits ordered trace_events (12)
│   │   ├── cost/
│   │   │   └── tracker.py          # token→USD, storage cost, break-even (13)
│   │   ├── schemas/                # pydantic: QueryRequest, QueryResponse, TraceEvent…
│   │   └── routers/
│   │       ├── health.py           # [scaffold]
│   │       ├── documents.py        # upload/list/delete (7)
│   │       ├── collections.py      # (7)
│   │       ├── query.py            # the core endpoint (11,12)
│   │       ├── inspector.py        # chunks, vectors, dry-run, scatter (8)
│   │       ├── settings.py         # storage backend get/set (10)
│   │       └── admin.py            # qdrant + pg stats (15)
│   └── tests/
│
├── infra/                          # config-only services + provisioning
│   ├── nginx/
│   │   ├── Dockerfile              # [scaffold]
│   │   └── nginx.conf              # [scaffold] routing + round-robin upstream (16)
│   ├── cloudflared/
│   │   └── README.md               # token via env; config in compose (17)
│   ├── qdrant/
│   │   └── cluster-config.yaml     # distributed-mode config, commented (1,6)
│   ├── setup-ubuntu.sh             # installs docker+compose on Ubuntu 22.04
│   ├── deploy.sh                   # zero-downtime pull + rolling restart
│   ├── aws-provision.sh            # creates S3 + 2 EBS, mounts, prints env (18)
│   └── aws-teardown.sh             # destroys the above — STOPS billing
│
├── scripts/
│   └── seed.py                     # loads NICE NG28 + PubMed + synthetic record (18)
│
├── data/                           # seed data (committed where licence allows)
│   ├── authoritative/              # guideline + abstract PDFs (or fetch-on-seed)
│   │   └── .gitkeep
│   ├── personal/
│   │   └── synthetic-patient-001.pdf   # clearly-marked SYNTHETIC record
│   └── README.md                   # provenance + licence notes per source
│
└── docs/
    ├── architecture.md             # [scaffold] (done)
    ├── folder-structure.md         # [scaffold] (this file)
    ├── self-hosting.md             # local / VPS in Local mode
    ├── cloudflare-tunnel.md        # create tunnel, token, custom domain, Access note
    ├── aws-storage.md              # S3 + EBS + IAM to switch to AWS mode
    └── scaling.md                  # local vols → EBS → cluster → S3; PG bottleneck
```

## Why this shape

- **Services with real source get top-level folders** (`frontend/`, `backend/`);
  pure-config services (nginx, cloudflared, qdrant) live under `infra/` so the
  root stays legible. docker-compose still treats all seven as separate services.
- **Every interface that the spec says must be extensible is its own module with
  a `base.py`** (`storage/`, `ingestion/handlers/`) so the extension point is
  obvious to a reviewer reading the tree.
- **`data/` separates `authoritative/` from `personal/`** at the filesystem level,
  mirroring the trust boundary the whole app is built around.
- **`infra/aws-teardown.sh` exists specifically** so a portfolio reviewer (or you)
  can't accidentally leave billable AWS resources running after a demo.

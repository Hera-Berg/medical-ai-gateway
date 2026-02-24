export type CorpusType = "authoritative" | "personal";

export interface Collection {
  id: string;
  name: string;
  corpus_type: CorpusType;
  qdrant_collection: string;
  description: string | null;
  created_at: string;
}

export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  storage_backend: string;
  source_version: string | null;
  published_date: string | null;
  source_url: string | null;
  chunk_count: number;
  uploaded_at: string;
}

const BASE = "/api";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail)
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listCollections: () =>
    fetch(`${BASE}/collections`).then((r) => jsonOrThrow<Collection[]>(r)),

  createCollection: (body: {
    name: string;
    corpus_type: CorpusType;
    description?: string;
  }) =>
    fetch(`${BASE}/collections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => jsonOrThrow<Collection>(r)),

  deleteCollection: (id: string) =>
    fetch(`${BASE}/collections/${id}`, { method: "DELETE" }).then((r) =>
      jsonOrThrow<{ deleted: string }>(r),
    ),

  listDocuments: (collectionId?: string) => {
    const q = collectionId ? `?collection_id=${collectionId}` : "";
    return fetch(`${BASE}/documents${q}`).then((r) =>
      jsonOrThrow<Document[]>(r),
    );
  },

  deleteDocument: (id: string) =>
    fetch(`${BASE}/documents/${id}`, { method: "DELETE" }).then((r) =>
      jsonOrThrow<{ deleted: string }>(r),
    ),

  uploadDocument: (params: {
    collectionId: string;
    file: File;
    sourceVersion?: string;
    sourceUrl?: string;
    publishedDate?: string;
  }) => {
    const fd = new FormData();
    fd.append("collection_id", params.collectionId);
    fd.append("file", params.file);
    if (params.sourceVersion) fd.append("source_version", params.sourceVersion);
    if (params.sourceUrl) fd.append("source_url", params.sourceUrl);
    if (params.publishedDate) fd.append("published_date", params.publishedDate);
    return fetch(`${BASE}/documents`, { method: "POST", body: fd }).then((r) =>
      jsonOrThrow<Document>(r),
    );
  },

  inspectorOverview: () =>
    fetch(`${BASE}/inspector/overview`).then((r) =>
      jsonOrThrow<InspectorOverview>(r),
    ),

  inspectorChunks: (collectionId: string) =>
    fetch(`${BASE}/inspector/collections/${collectionId}/chunks`).then((r) =>
      jsonOrThrow<InspectorChunks>(r),
    ),

  inspectorDryRun: (body: {
    query: string;
    collection_ids?: string[];
    limit?: number;
  }) =>
    fetch(`${BASE}/inspector/dry-run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => jsonOrThrow<DryRunResult>(r)),

  inspectorScatter: (collectionId: string) =>
    fetch(`${BASE}/inspector/collections/${collectionId}/scatter`).then((r) =>
      jsonOrThrow<ScatterResult>(r),
    ),

  getStorageSettings: () =>
    fetch(`${BASE}/settings/storage`).then((r) =>
      jsonOrThrow<StorageSettings>(r),
    ),

  storageReadiness: (name: string) =>
    fetch(`${BASE}/settings/storage/readiness/${name}`).then((r) =>
      jsonOrThrow<StorageReadiness>(r),
    ),

  switchStorageBackend: (backend: string, confirm: boolean) =>
    fetch(`${BASE}/settings/storage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend, confirm }),
    }).then((r) => jsonOrThrow<{ active: string; detail: string }>(r)),

  storageStats: () =>
    fetch(`${BASE}/admin/storage/stats`).then((r) =>
      jsonOrThrow<StorageStats>(r),
    ),

  adminCluster: () =>
    fetch(`${BASE}/admin/cluster`).then((r) => jsonOrThrow<AdminCluster>(r)),
  adminDatabase: () =>
    fetch(`${BASE}/admin/database`).then((r) => jsonOrThrow<AdminDatabase>(r)),

  costSummary: () =>
    fetch(`${BASE}/costs/summary`).then((r) => jsonOrThrow<CostSummary>(r)),
  costByModel: () =>
    fetch(`${BASE}/costs/by-model`).then((r) =>
      jsonOrThrow<{ by_model: CostByModel[] }>(r),
    ),
  costByTier: () =>
    fetch(`${BASE}/costs/by-tier`).then((r) =>
      jsonOrThrow<{ by_tier: CostByTier[] }>(r),
    ),
  costTimeline: () =>
    fetch(`${BASE}/costs/timeline`).then((r) =>
      jsonOrThrow<{ timeline: CostTimelinePoint[] }>(r),
    ),
  costRecent: () =>
    fetch(`${BASE}/costs/recent`).then((r) =>
      jsonOrThrow<{ recent: CostRecentRow[] }>(r),
    ),

  queryModels: () =>
    fetch(`${BASE}/query/models`).then((r) =>
      jsonOrThrow<QueryModelsResponse>(r),
    ),

  runQuery: (body: {
    question: string;
    model_key?: string;
    thinking_tier: "low" | "medium" | "high";
    collection_ids?: string[];
  }) =>
    fetch(`${BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => jsonOrThrow<QueryResponse>(r)),
};

export interface QueryModelsResponse {
  default: string;
  models: {
    key: string;
    display_name: string;
    gpu_tier: string;
    per_second_usd: number;
    capability_hint: string;
  }[];
  tiers: { key: string; multiplier: number; enabled: boolean }[];
}

export interface TraceChunk {
  rank: number;
  text: string;
  similarity_percent: number;
  source_filename: string;
  source_corpus_type: CorpusType;
  source_page: number | null;
  source_version: string | null;
}

export type TraceEventOut =
  | {
      type: "retrieval";
      sequence: number;
      query_text: string;
      chunks: TraceChunk[];
    }
  | {
      type: "inference_pass";
      sequence: number;
      role: string;
      label: string;
      output: string;
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
      latency_ms: number;
    };

export interface QueryResponse {
  query_id: string;
  answer: string;
  model: { key: string; display_name: string; gpu_tier: string };
  thinking_tier: string;
  mocked: boolean;
  trace_events: TraceEventOut[];
  cost: {
    n_inference_calls: number;
    total_input_tokens: number;
    total_output_tokens: number;
    total_cost_usd: number;
    total_latency_ms: number;
  };
}

export interface CostSummary {
  n_queries: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  avg_cost_per_query_usd: number;
  avg_latency_ms: number;
  total_inference_calls: number;
  break_even: {
    subscription_usd_month: number;
    subscription_label: string;
    queries_per_month_to_break_even: number | null;
    explanation: string;
  };
}
export interface CostByModel {
  model_key: string;
  n_queries: number;
  total_cost_usd: number;
  avg_cost_usd: number;
}
export interface CostByTier {
  tier: string;
  n_queries: number;
  total_cost_usd: number;
  avg_cost_usd: number;
  avg_inference_calls: number;
}
export interface CostTimelinePoint {
  day: string;
  n_queries: number;
  cost_usd: number;
}
export interface CostRecentRow {
  query_id: string;
  question: string;
  model_key: string;
  thinking_tier: string;
  n_inference_calls: number;
  total_cost_usd: number;
  total_latency_ms: number;
  created_at: string;
}

export interface StorageSettings {
  active: string;
  options: {
    name: string;
    label: string;
    tagline: string;
    description: string;
    requires_config: boolean;
  }[];
}

export interface StorageReadiness {
  name: string;
  ready: boolean;
  detail: string;
}

export interface StorageStats {
  backend_name: string;
  total_bytes: number;
  disk_usage_percent: number | null;
  estimated_monthly_cost_usd: number;
  disk_warning: boolean;
}

export interface AdminCluster {
  cluster: {
    status?: string;
    peer_id?: number;
    peer_count?: number;
    peers?: { peer_id: string; uri: string }[];
  };
  collections: {
    name: string;
    qdrant_collection: string;
    corpus_type: CorpusType;
    points_count: number | null;
    status: string | null;
    shard_number: number | null;
    replication_factor: number | null;
    shards: {
      peer_id?: number;
      shard_count?: number;
      local_shards?: { shard_id: number; state: string; points: number }[];
      remote_shards?: { shard_id: number; peer_id: number; state: string }[];
    };
  }[];
  caveat: string;
}

export interface AdminDatabase {
  row_counts: Record<string, number>;
  database_size: string | null;
}

export interface InspectorOverview {
  collections: {
    id: string;
    name: string;
    corpus_type: CorpusType;
    qdrant_collection: string;
    chunk_count: number;
    vector_count: number;
  }[];
  global_chunk_count: number;
  global_vector_count: number;
}

export interface InspectorChunk {
  id: string;
  chunk_index: number;
  text: string;
  page_number: number | null;
  section: string | null;
  token_count: number | null;
  vector: number[] | null;
  vector_dim: number | null;
}

export interface InspectorChunks {
  collection: { id: string; name: string; corpus_type: CorpusType };
  documents: {
    document_id: string;
    filename: string;
    source_version: string | null;
    chunk_count: number;
    chunks: InspectorChunk[];
  }[];
}

export interface DryRunResult {
  query: string;
  results: {
    text: string;
    similarity_score: number;
    similarity_percent: number;
    source_filename: string;
    source_corpus_type: CorpusType;
    source_collection_name: string;
    source_page: number | null;
    source_version: string | null;
  }[];
}

export interface ScatterResult {
  collection: { id: string; name: string; corpus_type: CorpusType };
  method: string;
  point_count: number;
  points: {
    x: number;
    y: number;
    text: string;
    page_number: number | null;
    filename: string | null;
  }[];
}

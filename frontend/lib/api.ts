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
};

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

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
};

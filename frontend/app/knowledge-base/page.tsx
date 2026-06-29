"use client";

/**
 * Knowledge Base — the document & collection management page.
 *
 * Layout: left column manages collections (create with corpus_type, select to
 * scope the view); right column is the upload dropzone + the document library
 * for the selected collection. The corpus-type distinction is visible at every
 * level via CorpusBadge.
 */
import { useCallback, useEffect, useState } from "react";
import { api, type Collection, type Document, type CorpusType } from "@/lib/api";
import { Button, Card, Input, Spinner, cn } from "@/components/ui/primitives";
import { CorpusBadge } from "@/components/corpus-badge";
import { UploadDropzone } from "@/components/knowledge-base/upload-dropzone";

export default function KnowledgeBasePage() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selected, setSelected] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [docsLoading, setDocsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // new-collection form
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState<CorpusType>("authoritative");
  const [creating, setCreating] = useState(false);

  const loadCollections = useCallback(async () => {
    setLoading(true);
    try {
      const cols = await api.listCollections();
      setCollections(cols);
      setSelected((prev) =>
        prev ? cols.find((c) => c.id === prev.id) ?? null : cols[0] ?? null
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDocuments = useCallback(async (collectionId: string) => {
    setDocsLoading(true);
    try {
      setDocuments(await api.listDocuments(collectionId));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCollections();
  }, [loadCollections]);

  useEffect(() => {
    if (selected) loadDocuments(selected.id);
    else setDocuments([]);
  }, [selected, loadDocuments]);

  const createCollection = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const col = await api.createCollection({
        name: newName.trim(),
        corpus_type: newType,
      });
      setNewName("");
      await loadCollections();
      setSelected(col);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

  const deleteCollection = async (c: Collection) => {
    if (
      !confirm(
        `Delete collection "${c.name}" and all its documents + vectors? This cannot be undone.`
      )
    )
      return;
    try {
      await api.deleteCollection(c.id);
      if (selected?.id === c.id) setSelected(null);
      await loadCollections();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const deleteDocument = async (d: Document) => {
    if (!confirm(`Delete "${d.filename}" and its ${d.chunk_count} chunks?`)) return;
    try {
      await api.deleteDocument(d.id);
      if (selected) loadDocuments(selected.id);
      loadCollections(); // chunk counts may inform UI later
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="space-y-6">
      <header className="fade-up">
        <h1 className="font-display text-3xl font-semibold text-ink">
          Knowledge Base
        </h1>
        <p className="mt-1 text-ink-soft">
          Manage the documents your queries draw on. Authoritative collections
          hold published literature; personal collections hold your own
          (synthetic) records.
        </p>
      </header>

      {error && (
        <div className="rounded-sm border border-[var(--danger)]/30 bg-[var(--warn-soft)] px-4 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        {/* ── Collections column ── */}
        <div className="space-y-4">
          <Card className="p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
              New collection
            </h2>
            <div className="space-y-2">
              <Input
                placeholder="Collection name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createCollection()}
              />
              <div className="grid grid-cols-2 gap-2">
                {(["authoritative", "personal"] as CorpusType[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setNewType(t)}
                    className={cn(
                      "rounded-sm border px-2 py-2 text-xs font-medium capitalize transition-colors",
                      newType === t
                        ? t === "authoritative"
                          ? "border-authoritative bg-authoritative-soft text-authoritative-ink"
                          : "border-personal bg-personal-soft text-personal-ink"
                        : "border-border text-ink-soft hover:bg-surface-2"
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <Button
                className="w-full"
                onClick={createCollection}
                disabled={creating || !newName.trim()}
              >
                {creating ? <Spinner /> : "Create collection"}
              </Button>
            </div>
          </Card>

          <div className="space-y-2">
            <h2 className="px-1 text-sm font-semibold uppercase tracking-wide text-ink-mute">
              Collections
            </h2>
            {loading ? (
              <div className="flex items-center gap-2 px-1 text-sm text-ink-mute">
                <Spinner /> Loading…
              </div>
            ) : collections.length === 0 ? (
              <p className="px-1 text-sm text-ink-mute">
                No collections yet. Create one to start.
              </p>
            ) : (
              collections.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelected(c)}
                  className={cn(
                    "group flex w-full items-center justify-between rounded border px-3 py-2.5 text-left transition-colors",
                    selected?.id === c.id
                      ? "border-brand bg-brand-soft"
                      : "border-border bg-surface hover:bg-surface-2"
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-ink">
                      {c.name}
                    </span>
                    <span className="mt-1 block">
                      <CorpusBadge type={c.corpus_type} />
                    </span>
                  </span>
                  <span
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteCollection(c);
                    }}
                    className="ml-2 shrink-0 rounded-sm px-2 py-1 text-xs text-ink-mute opacity-0 transition-opacity hover:text-danger group-hover:opacity-100"
                    role="button"
                    aria-label="Delete collection"
                  >
                    Delete
                  </span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* ── Documents column ── */}
        <div className="space-y-5">
          <Card className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-mute">
                Add documents
              </h2>
              {selected && <CorpusBadge type={selected.corpus_type} withHint />}
            </div>
            <UploadDropzone
              collectionId={selected?.id ?? null}
              disabled={!selected}
              onUploaded={(doc) => {
                setDocuments((prev) => [doc, ...prev]);
              }}
            />
          </Card>

          <Card className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-mute">
                Library
                {selected && (
                  <span className="ml-2 font-normal normal-case text-ink-mute">
                    · {selected.name}
                  </span>
                )}
              </h2>
              <span className="text-xs text-ink-mute">
                {documents.length} document{documents.length === 1 ? "" : "s"}
              </span>
            </div>

            {!selected ? (
              <p className="px-4 py-10 text-center text-sm text-ink-mute">
                Select a collection to view its documents.
              </p>
            ) : docsLoading ? (
              <div className="flex items-center justify-center gap-2 py-10 text-sm text-ink-mute">
                <Spinner /> Loading documents…
              </div>
            ) : documents.length === 0 ? (
              <p className="px-4 py-10 text-center text-sm text-ink-mute">
                No documents yet. Drop a PDF above to ingest one.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {documents.map((d) => (
                  <li
                    key={d.id}
                    className="flex items-center justify-between gap-4 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-ink">
                        {d.filename}
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-mute">
                        <span>
                          {new Date(d.uploaded_at).toLocaleDateString()}
                        </span>
                        <span className="font-medium text-brand-ink">
                          {d.chunk_count} chunks
                        </span>
                        {d.source_version && <span>· {d.source_version}</span>}
                        <span className="rounded-sm bg-surface-2 px-1.5 py-0.5">
                          {d.storage_backend}
                        </span>
                      </div>
                    </div>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => deleteDocument(d)}
                    >
                      Delete
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

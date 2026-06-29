"use client";

/**
 * RAG Inspector — the developer/diagnostic page. Explicitly labelled as such.
 * Surfaces the retrieval internals: counts, a live no-LLM similarity dry-run,
 * the PCA scatter of the vector space, and a full chunk+vector browser.
 *
 * Everything here reads the same retrieval pipeline the chat will use, so it's a
 * faithful diagnostic — not a separate mock.
 */
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type InspectorOverview,
  type InspectorChunks,
  type DryRunResult,
  type ScatterResult,
} from "@/lib/api";
import { Button, Card, Input, Spinner, cn } from "@/components/ui/primitives";
import { CorpusBadge } from "@/components/corpus-badge";
import { ScatterPlot } from "@/components/rag-inspector/scatter-plot";
import { ChunkRow } from "@/components/rag-inspector/chunk-row";

export default function RagInspectorPage() {
  const [overview, setOverview] = useState<InspectorOverview | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<InspectorChunks | null>(null);
  const [scatter, setScatter] = useState<ScatterResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);

  // dry-run search
  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<DryRunResult | null>(null);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    try {
      const ov = await api.inspectorOverview();
      setOverview(ov);
      setSelectedId((prev) => prev ?? ov.collections[0]?.id ?? null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    (async () => {
      setDetailLoading(true);
      setChunks(null);
      setScatter(null);
      try {
        const [ch, sc] = await Promise.all([
          api.inspectorChunks(selectedId),
          api.inspectorScatter(selectedId),
        ]);
        if (!cancelled) {
          setChunks(ch);
          setScatter(sc);
        }
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const runSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      setResults(
        await api.inspectorDryRun({ query: query.trim(), limit: 8 })
      );
    } finally {
      setSearching(false);
    }
  };

  const selectedCollection = overview?.collections.find((c) => c.id === selectedId);
  const accentVar =
    selectedCollection?.corpus_type === "personal"
      ? "--personal"
      : "--authoritative";

  return (
    <div className="space-y-6">
      <header className="fade-up">
        <div className="flex items-center gap-3">
          <h1 className="font-display text-3xl font-semibold text-ink">
            RAG Inspector
          </h1>
          <span className="rounded-sm bg-ink px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-white">
            Developer / diagnostic tool
          </span>
        </div>
        <p className="mt-1 text-ink-soft">
          Inspect the vector index directly: browse chunks and their embeddings,
          run a live similarity search with no LLM in the loop, and see the
          embedding space projected to 2D.
        </p>
      </header>

      {/* ── global + per-collection counts ── */}
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-ink-mute">
          <Spinner /> Loading index…
        </div>
      ) : !overview || overview.collections.length === 0 ? (
        <Card className="p-8 text-center text-sm text-ink-mute">
          Nothing indexed yet. Add documents in the Knowledge Base first.
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Collections" value={overview.collections.length} />
            <Stat label="Total chunks" value={overview.global_chunk_count} />
            <Stat label="Total vectors" value={overview.global_vector_count} />
            <Stat
              label="Vector dims"
              value={384}
              hint="bge-small-en-v1.5"
            />
          </div>

          {/* ── live dry-run search ── */}
          <Card className="p-4">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-ink-mute">
              Live retrieval dry-run
            </h2>
            <p className="mb-3 text-xs text-ink-mute">
              Type a query to see which chunks would be retrieved, ranked by
              cosine similarity. No LLM is called — this is pure vector search
              across all collections.
            </p>
            <div className="flex gap-2">
              <Input
                placeholder="e.g. What is the HbA1c target for type 2 diabetes?"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runSearch()}
              />
              <Button onClick={runSearch} disabled={searching || !query.trim()}>
                {searching ? <Spinner /> : "Search"}
              </Button>
            </div>

            {results && (
              <div className="mt-4 space-y-2">
                {results.results.length === 0 ? (
                  <p className="text-sm text-ink-mute">No matches.</p>
                ) : (
                  results.results.map((r, i) => (
                    <div
                      key={i}
                      className="rounded-sm border border-border bg-surface-2 p-3"
                    >
                      <div className="mb-1.5 flex items-center gap-2">
                        <span className="rounded-sm bg-brand px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white">
                          {r.similarity_percent}%
                        </span>
                        <CorpusBadge type={r.source_corpus_type} />
                        <span className="truncate text-xs text-ink-mute">
                          {r.source_filename}
                          {r.source_page != null && ` · p.${r.source_page}`}
                        </span>
                      </div>
                      <p className="text-sm text-ink">{r.text}</p>
                    </div>
                  ))
                )}
              </div>
            )}
          </Card>

          {/* ── collection selector ── */}
          <div className="flex flex-wrap gap-2">
            {overview.collections.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelectedId(c.id)}
                className={cn(
                  "flex items-center gap-2 rounded border px-3 py-1.5 text-sm transition-colors",
                  selectedId === c.id
                    ? "border-brand bg-brand-soft text-brand-ink"
                    : "border-border bg-surface hover:bg-surface-2"
                )}
              >
                {c.name}
                <span className="text-xs text-ink-mute">
                  {c.vector_count} vec
                </span>
              </button>
            ))}
          </div>

          {detailLoading ? (
            <div className="flex items-center gap-2 text-sm text-ink-mute">
              <Spinner /> Loading collection…
            </div>
          ) : (
            <>
              {/* ── scatter plot ── */}
              {scatter && (
                <Card className="p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-mute">
                      Embedding space (2D PCA)
                    </h2>
                    {selectedCollection && (
                      <CorpusBadge type={selectedCollection.corpus_type} />
                    )}
                  </div>
                  <ScatterPlot data={scatter} accent={accentVar} />
                </Card>
              )}

              {/* ── chunk browser ── */}
              {chunks && (
                <Card className="p-4">
                  <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
                    Indexed chunks
                  </h2>
                  <div className="space-y-4">
                    {chunks.documents.map((doc) => (
                      <div key={doc.document_id}>
                        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
                          {doc.filename}
                          <span className="text-xs font-normal text-ink-mute">
                            {doc.chunk_count} chunks
                            {doc.source_version && ` · ${doc.source_version}`}
                          </span>
                        </div>
                        <div className="space-y-1.5">
                          {doc.chunks.map((ch) => (
                            <ChunkRow key={ch.id} chunk={ch} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <Card className="px-4 py-3">
      <div className="text-2xl font-semibold text-ink">{value.toLocaleString()}</div>
      <div className="text-xs text-ink-mute">{label}</div>
      {hint && <div className="mt-0.5 font-mono text-[10px] text-ink-mute">{hint}</div>}
    </Card>
  );
}

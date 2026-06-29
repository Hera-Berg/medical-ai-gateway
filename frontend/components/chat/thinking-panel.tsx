"use client";

/**
 * ThinkingPanel — renders the ordered trace (retrieval + inference passes) for a
 * chat answer. Collapsed by default so the answer leads; expand to see how it
 * was reached. Each retrieval event shows the (possibly reframed) query that
 * pass used and the chunks it pulled, with a subtle corpus badge so the
 * authoritative-vs-personal provenance is visible across the trust boundary.
 *
 * Honest framing: chunk cards say "Retrieved from [source] · NN%" — never
 * "verified". They show where evidence came from, not that it's correct.
 */
import { useState } from "react";
import type { TraceEventOut } from "@/lib/api";
import { CorpusBadge } from "@/components/corpus-badge";
import { cn } from "@/components/ui/primitives";

export function ThinkingPanel({
  events,
  nCalls,
}: {
  events: TraceEventOut[];
  nCalls: number;
}) {
  const [open, setOpen] = useState(false);

  // pair each inference pass with the retrieval that preceded it (if any)
  const retrievals = events.filter((e) => e.type === "retrieval");
  const passes = events.filter((e) => e.type === "inference_pass");

  return (
    <div className="mt-3 rounded-md border border-border bg-surface-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
      >
        <span className="font-medium text-ink-soft">
          Thinking transparency
          <span className="ml-2 font-normal text-ink-mute">
            {nCalls} inference {nCalls === 1 ? "pass" : "passes"} ·{" "}
            {retrievals.length} retrieval{retrievals.length === 1 ? "" : "s"}
          </span>
        </span>
        <span className={cn("text-ink-mute transition-transform", open && "rotate-90")}>
          ›
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-border px-3 py-3">
          {events.map((ev, i) =>
            ev.type === "retrieval" ? (
              <RetrievalStep key={i} ev={ev} />
            ) : (
              <PassStep key={i} ev={ev} />
            )
          )}
        </div>
      )}
    </div>
  );
}

function RetrievalStep({
  ev,
}: {
  ev: Extract<TraceEventOut, { type: "retrieval" }>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-sm border border-border bg-surface">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start gap-2 px-3 py-2 text-left"
      >
        <span className="mt-0.5 rounded-sm bg-ink/5 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-mute">
          Retrieval
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-xs text-ink-mute">searched for</span>
          <span className="block truncate text-sm text-ink-soft">
            {ev.query_text}
          </span>
        </span>
        <span className="shrink-0 text-xs text-ink-mute">
          {ev.chunks.length} chunks
        </span>
      </button>
      {open && (
        <div className="space-y-1.5 border-t border-border px-3 py-2">
          {ev.chunks.map((c) => (
            <div key={c.rank} className="rounded-sm bg-surface-2 p-2">
              <div className="mb-1 flex items-center gap-2">
                <span className="rounded-sm bg-brand px-1.5 py-0.5 font-mono text-[10px] font-semibold text-white">
                  {c.similarity_percent}%
                </span>
                <CorpusBadge type={c.source_corpus_type} />
                <span className="truncate text-[11px] text-ink-mute">
                  Retrieved from {c.source_filename}
                  {c.source_page != null && ` · p.${c.source_page}`}
                </span>
              </div>
              <p className="line-clamp-3 text-xs text-ink-soft">{c.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PassStep({
  ev,
}: {
  ev: Extract<TraceEventOut, { type: "inference_pass" }>;
}) {
  return (
    <div className="rounded-sm border border-[var(--brand)]/20 bg-[var(--brand-soft)]/40 px-3 py-2">
      <div className="mb-1 flex items-center justify-between">
        <span className="text-sm font-medium text-brand-ink">{ev.label}</span>
        <span className="font-mono text-[11px] text-ink-mute">
          {(ev.latency_ms / 1000).toFixed(1)}s · ${ev.cost_usd.toFixed(5)}
        </span>
      </div>
      <p className="text-sm text-ink">{ev.output}</p>
    </div>
  );
}

"use client";

/**
 * ChunkRow — one chunk in the inspector's browse view. Shows index, page, token
 * count, the text, and the embedding vector truncated to the first 8 dimensions
 * with a "copy full vector" button (per spec).
 */
import { useState } from "react";
import type { InspectorChunk } from "@/lib/api";
import { cn } from "@/components/ui/primitives";

export function ChunkRow({ chunk }: { chunk: InspectorChunk }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const preview = chunk.vector ? chunk.vector.slice(0, 8) : [];

  const copyVector = async () => {
    if (!chunk.vector) return;
    await navigator.clipboard.writeText(JSON.stringify(chunk.vector));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-sm border border-border bg-surface">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-surface-2"
      >
        <span className="font-mono text-xs text-ink-mute">#{chunk.chunk_index}</span>
        <span className="min-w-0 flex-1 truncate text-sm text-ink">
          {chunk.text.slice(0, 110)}
          {chunk.text.length > 110 ? "…" : ""}
        </span>
        <span className="shrink-0 text-[11px] text-ink-mute">
          {chunk.page_number != null && `p.${chunk.page_number} · `}
          {chunk.token_count}t
        </span>
        <span className={cn("shrink-0 text-ink-mute transition-transform", open && "rotate-90")}>
          ›
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-border px-3 py-3">
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-ink-mute">
              Chunk text
            </div>
            <p className="whitespace-pre-wrap rounded-sm bg-surface-2 p-2 text-sm text-ink">
              {chunk.text}
            </p>
          </div>

          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-[11px] font-medium uppercase tracking-wide text-ink-mute">
                Embedding vector{" "}
                {chunk.vector_dim && (
                  <span className="font-normal normal-case">
                    ({chunk.vector_dim} dims, showing 8)
                  </span>
                )}
              </span>
              {chunk.vector && (
                <button
                  onClick={copyVector}
                  className="rounded-sm border border-border px-2 py-0.5 text-[11px] text-ink-soft hover:bg-surface-2"
                >
                  {copied ? "Copied!" : "Copy full vector"}
                </button>
              )}
            </div>
            {chunk.vector ? (
              <code className="block overflow-x-auto rounded-sm bg-ink/[0.03] p-2 font-mono text-xs text-ink-soft">
                [{preview.map((v) => v.toFixed(5)).join(", ")}
                {chunk.vector.length > 8 ? ", …" : ""}]
              </code>
            ) : (
              <span className="text-xs text-ink-mute">
                vector not found in Qdrant
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

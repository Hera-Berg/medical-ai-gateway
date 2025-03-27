"use client";

import { useCallback, useRef, useState } from "react";
import { api, type Document } from "@/lib/api";
import { Button, Spinner, cn } from "@/components/ui/primitives";

const STAGES = [
  "Storing",
  "Parsing",
  "Chunking",
  "Embedding",
  "Indexing",
] as const;

export function UploadDropzone({
  collectionId,
  disabled,
  onUploaded,
}: {
  collectionId: string | null;
  disabled?: boolean;
  onUploaded: (doc: Document) => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [sourceVersion, setSourceVersion] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const runUpload = useCallback(
    async (file: File) => {
      if (!collectionId) {
        setError("Select or create a collection first.");
        return;
      }
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("PDF only for now.");
        return;
      }
      setError(null);
      setBusy(true);
      setStageIdx(0);
      timer.current = setInterval(() => {
        setStageIdx((i) => Math.min(i + 1, STAGES.length - 1));
      }, 600);

      try {
        const doc = await api.uploadDocument({
          collectionId,
          file,
          sourceVersion: sourceVersion || undefined,
        });
        onUploaded(doc);
        setSourceVersion("");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (timer.current) clearInterval(timer.current);
        setBusy(false);
        setStageIdx(0);
      }
    },
    [collectionId, sourceVersion, onUploaded],
  );

  return (
    <div className="space-y-3">
      <input
        type="text"
        value={sourceVersion}
        onChange={(e) => setSourceVersion(e.target.value)}
        placeholder="Source / version label (optional) — e.g. NICE NG28 (2026)"
        disabled={busy || disabled}
        className="w-full rounded-sm border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-mute focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/20"
      />

      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !busy) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) runUpload(f);
        }}
        onClick={() => !busy && !disabled && inputRef.current?.click()}
        className={cn(
          "flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded border-2 border-dashed px-6 py-8 text-center transition-colors",
          dragOver
            ? "border-brand bg-brand-soft"
            : "border-border-strong bg-surface-2 hover:border-brand/60",
          (disabled || busy) && "cursor-not-allowed opacity-70",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) runUpload(f);
            e.target.value = "";
          }}
        />

        {!busy ? (
          <>
            <div className="font-display text-lg text-ink">
              Drop a PDF to ingest
            </div>
            <div className="mt-1 text-sm text-ink-mute">
              {disabled
                ? "Select a collection first"
                : "or click to choose a file · PDF only"}
            </div>
          </>
        ) : (
          <div className="w-full max-w-sm">
            <div className="mb-3 flex items-center justify-center gap-2 text-sm text-ink-soft">
              <Spinner className="text-brand" />
              Ingesting…
            </div>
            <div className="flex flex-wrap items-center justify-center gap-1.5">
              {STAGES.map((s, i) => (
                <span
                  key={s}
                  className={cn(
                    "rounded-sm px-2 py-1 text-xs transition-colors",
                    i < stageIdx && "bg-brand-soft text-brand-ink",
                    i === stageIdx && "stage-active bg-brand text-white",
                    i > stageIdx && "bg-surface text-ink-mute",
                  )}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-sm border border-[var(--danger)]/30 bg-[var(--warn-soft)] px-3 py-2 text-sm text-danger">
          {error}
        </div>
      )}
    </div>
  );
}

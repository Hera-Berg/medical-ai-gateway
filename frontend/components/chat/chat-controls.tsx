"use client";

/**
 * ChatControls — model selector, thinking-tier selector (with cost-multiplier
 * preview so the depth/cost tradeoff is visible before submitting), and the
 * collection scope picker. Lifted state: the parent owns the values.
 */
import type { QueryModelsResponse } from "@/lib/api";
import type { Collection } from "@/lib/api";
import { cn } from "@/components/ui/primitives";
import { CorpusBadge } from "@/components/corpus-badge";

const TIER_LABELS: Record<string, { name: string; desc: string }> = {
  low: { name: "Low", desc: "1 pass — fast lookup" },
  medium: { name: "Medium", desc: "3 passes — propose, challenge, reconcile" },
  high: { name: "High", desc: "6 passes — deep multi-stage scrutiny" },
};

export function ChatControls({
  models,
  selectedModel,
  onModel,
  tiers,
  selectedTier,
  onTier,
  collections,
  selectedCollections,
  onToggleCollection,
  disabled,
}: {
  models: QueryModelsResponse["models"];
  selectedModel: string;
  onModel: (k: string) => void;
  tiers: QueryModelsResponse["tiers"];
  selectedTier: string;
  onTier: (k: string) => void;
  collections: Collection[];
  selectedCollections: string[]; // empty = all
  onToggleCollection: (id: string) => void;
  disabled: boolean;
}) {
  const model = models.find((m) => m.key === selectedModel);

  return (
    <div className="space-y-4">
      {/* model */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-mute">
          Model
        </label>
        <div className="flex flex-wrap gap-2">
          {models.map((m) => (
            <button
              key={m.key}
              disabled={disabled}
              onClick={() => onModel(m.key)}
              className={cn(
                "rounded border px-3 py-1.5 text-left text-sm transition-colors disabled:opacity-50",
                m.key === selectedModel
                  ? "border-brand bg-brand-soft text-brand-ink"
                  : "border-border bg-surface hover:bg-surface-2"
              )}
            >
              <span className="block font-medium">{m.display_name}</span>
              <span className="block text-[11px] text-ink-mute">{m.gpu_tier}</span>
            </button>
          ))}
        </div>
        {model && (
          <p className="mt-1.5 text-xs text-ink-mute">{model.capability_hint}</p>
        )}
      </div>

      {/* thinking tier */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-mute">
          Thinking depth
        </label>
        <div className="grid grid-cols-3 gap-2">
          {tiers.map((t) => {
            const meta = TIER_LABELS[t.key] ?? { name: t.key, desc: "" };
            return (
              <button
                key={t.key}
                disabled={disabled || !t.enabled}
                onClick={() => onTier(t.key)}
                className={cn(
                  "rounded border px-3 py-2 text-left transition-colors disabled:opacity-40",
                  t.key === selectedTier
                    ? "border-brand bg-brand-soft text-brand-ink"
                    : "border-border bg-surface hover:bg-surface-2"
                )}
              >
                <span className="flex items-center justify-between">
                  <span className="text-sm font-medium">{meta.name}</span>
                  <span className="rounded-sm bg-ink/5 px-1 text-[10px] font-semibold text-ink-mute">
                    {t.multiplier}×
                  </span>
                </span>
                <span className="mt-0.5 block text-[11px] text-ink-mute">
                  {meta.desc}
                </span>
              </button>
            );
          })}
        </div>
        <p className="mt-1.5 text-xs text-ink-mute">
          Higher depth runs more inference passes (more retrieval + scrutiny) —
          roughly proportional cost. Depth is thoroughness, not guaranteed
          accuracy.
        </p>
      </div>

      {/* collection scope */}
      {collections.length > 0 && (
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-mute">
            Corpora{" "}
            <span className="font-normal normal-case text-ink-mute">
              ({selectedCollections.length === 0 ? "all" : selectedCollections.length} selected)
            </span>
          </label>
          <div className="flex flex-wrap gap-2">
            {collections.map((c) => {
              const on =
                selectedCollections.length === 0 ||
                selectedCollections.includes(c.id);
              return (
                <button
                  key={c.id}
                  disabled={disabled}
                  onClick={() => onToggleCollection(c.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs transition-colors disabled:opacity-50",
                    on
                      ? "border-brand bg-brand-soft"
                      : "border-border bg-surface opacity-50"
                  )}
                >
                  <CorpusBadge type={c.corpus_type} />
                  {c.name}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

/**
 * CorpusBadge — the visual identity of the trust boundary.
 *
 * This is the single most-repeated meaningful element in the app: it appears on
 * collections, document rows, chunk cards, the inspector, and the thinking
 * panel. Authoritative (published literature) and personal (the user's own
 * record) each have a consistent colour + label everywhere, so a user can tell
 * at a glance which side of the boundary any piece of evidence came from.
 *
 * Keeping it in ONE component means the distinction can never drift between
 * pages.
 */
import { Badge } from "@/components/ui/primitives";

export type CorpusType = "authoritative" | "personal";

const CONFIG: Record<
  CorpusType,
  { label: string; cls: string; dot: string; hint: string }
> = {
  authoritative: {
    label: "Authoritative",
    cls: "bg-authoritative-soft text-authoritative-ink",
    dot: "bg-authoritative",
    hint: "Published literature & guidelines",
  },
  personal: {
    label: "Personal",
    cls: "bg-personal-soft text-personal-ink",
    dot: "bg-personal",
    hint: "Your own (synthetic) record",
  },
};

export function CorpusBadge({
  type,
  withHint = false,
}: {
  type: CorpusType;
  withHint?: boolean;
}) {
  const c = CONFIG[type] ?? CONFIG.authoritative;
  return (
    <Badge className={c.cls} title={c.hint}>
      <span className={`h-1.5 w-1.5 rounded-full ${c.dot}`} />
      {c.label}
      {withHint && <span className="font-normal opacity-70">· {c.hint}</span>}
    </Badge>
  );
}

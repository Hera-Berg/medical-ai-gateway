"use client";

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

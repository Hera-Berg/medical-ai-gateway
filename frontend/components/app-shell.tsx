"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/components/ui/primitives";

const NAV: { href: string; label: string; desc: string }[] = [
  { href: "/", label: "Chat", desc: "Ask across your corpora" },
  {
    href: "/knowledge-base",
    label: "Knowledge Base",
    desc: "Documents & collections",
  },
  { href: "/rag-inspector", label: "RAG Inspector", desc: "Diagnostic" },
  {
    href: "/cost-dashboard",
    label: "Cost Dashboard",
    desc: "Spend & break-even",
  },
  { href: "/settings", label: "Settings", desc: "Storage backend" },
  { href: "/admin", label: "Admin", desc: "Cluster & DB stats" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="relative z-10 mx-auto flex min-h-[calc(100vh-2.5rem)] max-w-[1400px] gap-0">
      {/* ── Navigation rail ── */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-surface/60 px-4 py-6 backdrop-blur md:flex">
        <Link href="/" className="mb-8 block px-2">
          <div className="font-display text-xl font-semibold leading-tight text-ink">
            Medical AI
            <br />
            Gateway
          </div>
          <div className="mt-1 text-[11px] uppercase tracking-wider text-ink-mute">
            cost-transparent rag
          </div>
        </Link>

        <nav className="flex flex-col gap-1">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group rounded px-3 py-2 transition-colors",
                  active
                    ? "bg-brand-soft text-brand-ink"
                    : "text-ink-soft hover:bg-surface-2 hover:text-ink",
                )}
              >
                <div className="text-sm font-medium">{item.label}</div>
                <div
                  className={cn(
                    "text-[11px]",
                    active ? "text-brand/70" : "text-ink-mute",
                  )}
                >
                  {item.desc}
                </div>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto rounded-sm border border-border bg-surface-2 px-3 py-2 text-[11px] leading-relaxed text-ink-mute">
          Demo &amp; educational tool. Not medical advice. Synthetic records
          only.
        </div>
      </aside>

      {/* ── Content ── */}
      <main className="min-w-0 flex-1 px-6 py-8 md:px-10">{children}</main>
    </div>
  );
}

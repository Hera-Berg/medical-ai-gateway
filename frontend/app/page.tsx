"use client";

import { useEffect, useState } from "react";

type Health = { status?: string; replica?: string };
type Ready = { ready?: boolean; dependencies?: Record<string, string> };

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [ready, setReady] = useState<Ready | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [h, r] = await Promise.all([
          fetch("/api/health").then((x) => x.json()),
          fetch("/api/ready").then((x) => x.json()),
        ]);
        setHealth(h);
        setReady(r);
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">
          Medical AI Gateway
        </h1>
        <p className="mt-1 text-neutral-600">
          Cost-transparent · data-sovereign · domain-specialised RAG
        </p>
      </header>

      <section className="rounded-lg border border-neutral-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
          Scaffold self-check
        </h2>
        {error && (
          <p className="text-sm text-red-600">
            Backend unreachable: {error} — is the stack up?
          </p>
        )}
        {!error && (
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <dt className="text-neutral-500">Backend liveness</dt>
            <dd className="font-mono">{health?.status ?? "…"}</dd>
            <dt className="text-neutral-500">Serving replica</dt>
            <dd className="font-mono">{health?.replica ?? "…"}</dd>
            <dt className="text-neutral-500">Dependencies ready</dt>
            <dd className="font-mono">{ready ? String(ready.ready) : "…"}</dd>
            <dt className="text-neutral-500">Qdrant nodes</dt>
            <dd className="font-mono">
              {ready?.dependencies
                ? Object.entries(ready.dependencies)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(" · ")
                : "…"}
            </dd>
          </dl>
        )}
        <p className="mt-4 text-xs text-neutral-400">
          Refresh a few times — the serving replica should rotate as Nginx
          round-robins across backend instances.
        </p>
      </section>
    </div>
  );
}

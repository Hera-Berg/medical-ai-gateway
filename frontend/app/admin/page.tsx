"use client";

import { useEffect, useState } from "react";
import { api, type AdminCluster, type AdminDatabase } from "@/lib/api";
import { Card, Spinner } from "@/components/ui/primitives";
import { CorpusBadge } from "@/components/corpus-badge";

export default function AdminPage() {
  const [cluster, setCluster] = useState<AdminCluster | null>(null);
  const [database, setDatabase] = useState<AdminDatabase | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, d] = await Promise.all([
          api.adminCluster().catch(() => null),
          api.adminDatabase().catch(() => null),
        ]);
        setCluster(c);
        setDatabase(d);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <header className="fade-up">
        <h1 className="font-display text-3xl font-semibold text-ink">Admin</h1>
        <p className="mt-1 text-ink-soft">
          Cluster topology and database stats — the operational internals.
        </p>
      </header>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-ink-mute">
          <Spinner /> Loading admin stats…
        </div>
      ) : (
        <>
          {/* ── Qdrant cluster ── */}
          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
              Qdrant cluster
            </h2>

            {cluster?.cluster?.peer_count ? (
              <div className="mb-4 flex flex-wrap gap-3">
                <Mini label="Status" value={cluster.cluster.status ?? "—"} />
                <Mini
                  label="Nodes (peers)"
                  value={String(cluster.cluster.peer_count)}
                />
                <Mini
                  label="This peer"
                  value={
                    cluster.cluster.peer_id
                      ? `#${cluster.cluster.peer_id}`
                      : "—"
                  }
                />
              </div>
            ) : (
              <p className="mb-4 text-sm text-ink-mute">
                Cluster API not reachable (single-node dev, or cluster not
                formed).
              </p>
            )}

            {/* honest caveat */}
            {cluster?.caveat && (
              <div className="mb-4 rounded-sm border border-warn/30 bg-[var(--warn-soft)] px-3 py-2 text-xs text-warn">
                <strong>Topology demo, not fault tolerance.</strong>{" "}
                {cluster.caveat}
              </div>
            )}

            {/* per-collection shard placement */}
            <div className="space-y-3">
              {cluster?.collections.map((c) => (
                <div
                  key={c.qdrant_collection}
                  className="rounded-sm border border-border bg-surface p-3"
                >
                  <div className="mb-2 flex items-center gap-2">
                    <span className="font-medium text-ink">{c.name}</span>
                    <CorpusBadge type={c.corpus_type} />
                    <span className="ml-auto text-xs text-ink-mute">
                      {c.points_count ?? "—"} points · {c.status ?? "—"}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-ink-soft">
                    <span>
                      shards: <strong>{c.shard_number ?? "—"}</strong>
                    </span>
                    <span>
                      replication:{" "}
                      <strong>{c.replication_factor ?? "—"}×</strong>
                    </span>
                    {c.shards?.local_shards &&
                      c.shards.local_shards.length > 0 && (
                        <span>
                          local shards on this peer:{" "}
                          <strong>
                            {c.shards.local_shards
                              .map((s) => `#${s.shard_id} (${s.state})`)
                              .join(", ")}
                          </strong>
                        </span>
                      )}
                    {c.shards?.remote_shards &&
                      c.shards.remote_shards.length > 0 && (
                        <span>
                          remote shards:{" "}
                          <strong>
                            {c.shards.remote_shards
                              .map(
                                (s) =>
                                  `#${s.shard_id}→peer ${s.peer_id} (${s.state})`,
                              )
                              .join(", ")}
                          </strong>
                        </span>
                      )}
                  </div>
                </div>
              ))}
              {(!cluster || cluster.collections.length === 0) && (
                <p className="text-sm text-ink-mute">No collections yet.</p>
              )}
            </div>
          </Card>

          {/* ── Postgres ── */}
          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
              Database (Postgres)
            </h2>
            {database ? (
              <>
                <div className="flex flex-wrap gap-3">
                  {Object.entries(database.row_counts).map(([table, n]) => (
                    <Mini
                      key={table}
                      label={table}
                      value={n.toLocaleString()}
                    />
                  ))}
                  {database.database_size && (
                    <Mini label="DB size" value={database.database_size} />
                  )}
                </div>
                <p className="mt-3 text-xs text-ink-mute">
                  Single Postgres instance — a deliberate, documented bottleneck
                  (the stateless backend scales horizontally; the database does
                  not, in this demo).
                </p>
              </>
            ) : (
              <p className="text-sm text-ink-mute">
                Database stats unavailable.
              </p>
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-sm border border-border bg-surface px-3 py-2">
      <div className="font-display text-xl font-semibold text-ink">{value}</div>
      <div className="text-[11px] capitalize text-ink-mute">{label}</div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import {
  api,
  type CostSummary,
  type CostByModel,
  type CostByTier,
  type CostTimelinePoint,
  type CostRecentRow,
} from "@/lib/api";
import { Card, Spinner } from "@/components/ui/primitives";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

function usd(n: number, dp = 4): string {
  return `$${n.toFixed(dp)}`;
}

export default function CostDashboardPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [byModel, setByModel] = useState<CostByModel[]>([]);
  const [byTier, setByTier] = useState<CostByTier[]>([]);
  const [timeline, setTimeline] = useState<CostTimelinePoint[]>([]);
  const [recent, setRecent] = useState<CostRecentRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, m, t, tl, r] = await Promise.all([
          api.costSummary(),
          api.costByModel(),
          api.costByTier(),
          api.costTimeline(),
          api.costRecent(),
        ]);
        setSummary(s);
        setByModel(m.by_model);
        setByTier(t.by_tier);
        setTimeline(tl.timeline);
        setRecent(r.recent);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <header className="fade-up">
        <h1 className="font-display text-3xl font-semibold text-ink">
          Cost Dashboard
        </h1>
        <p className="mt-1 text-ink-soft">
          Real per-query spend, measured from RunPod’s per-second GPU billing —
          not estimated from tokens.
        </p>
      </header>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-ink-mute">
          <Spinner /> Loading cost data…
        </div>
      ) : !summary || summary.n_queries === 0 ? (
        <Card className="p-8 text-center text-sm text-ink-mute">
          No queries logged yet. Run a query from Chat (or the API) to see costs
          appear here.
        </Card>
      ) : (
        <>
          {/* ── summary stats ── */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Total queries" value={String(summary.n_queries)} />
            <Stat label="Total spend" value={usd(summary.total_cost_usd, 4)} />
            <Stat
              label="Avg / query"
              value={usd(summary.avg_cost_per_query_usd, 5)}
            />
            <Stat
              label="Inference calls"
              value={String(summary.total_inference_calls)}
            />
          </div>

          {/* ── break-even widget ── */}
          <Card className="border-brand/30 bg-brand-soft p-5">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-brand-ink">
              Break-even vs {summary.break_even.subscription_label}
            </h2>
            {summary.break_even.queries_per_month_to_break_even != null ? (
              <>
                <div className="flex items-baseline gap-2">
                  <span className="font-display text-4xl font-semibold text-ink">
                    {Math.round(
                      summary.break_even.queries_per_month_to_break_even,
                    ).toLocaleString()}
                  </span>
                  <span className="text-ink-soft">queries / month</span>
                </div>
                <p className="mt-2 max-w-2xl text-sm text-ink-soft">
                  At your measured average of{" "}
                  <strong>{usd(summary.avg_cost_per_query_usd, 5)}</strong> per
                  query, you could run{" "}
                  <strong>
                    {Math.round(
                      summary.break_even.queries_per_month_to_break_even,
                    ).toLocaleString()}
                  </strong>{" "}
                  queries a month before self-hosting costs as much as the{" "}
                  {summary.break_even.subscription_label}. Below that,
                  per-second self-hosting is cheaper.
                </p>
              </>
            ) : (
              <p className="text-sm text-ink-soft">
                Not enough data to compute break-even yet.
              </p>
            )}
          </Card>

          {/* ── spend over time ── */}
          {timeline.length > 0 && (
            <Card className="p-5">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-ink-mute">
                Spend over time
              </h2>
              <div style={{ width: "100%", height: 260 }}>
                <ResponsiveContainer>
                  <LineChart
                    data={timeline}
                    margin={{ left: 8, right: 8, top: 8 }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="var(--border)"
                    />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11 }}
                      stroke="var(--ink-mute)"
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      stroke="var(--ink-mute)"
                      tickFormatter={(v) => `$${v}`}
                    />
                    <Tooltip
                      formatter={(v: number) => [usd(v, 5), "spend"]}
                      contentStyle={{
                        fontSize: 12,
                        borderRadius: 6,
                        border: "1px solid var(--border)",
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="cost_usd"
                      stroke="var(--brand)"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          )}

          {/* ── breakdowns ── */}
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
                By thinking tier
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ink-mute">
                    <th className="pb-2 font-medium">Tier</th>
                    <th className="pb-2 font-medium">Queries</th>
                    <th className="pb-2 font-medium">Avg calls</th>
                    <th className="pb-2 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {byTier.map((t) => (
                    <tr key={t.tier} className="border-t border-border">
                      <td className="py-2 capitalize text-ink">{t.tier}</td>
                      <td className="py-2 text-ink-soft">{t.n_queries}</td>
                      <td className="py-2 text-ink-soft">
                        {t.avg_inference_calls}
                      </td>
                      <td className="py-2 text-right font-mono text-ink">
                        {usd(t.total_cost_usd, 5)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>

            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
                By model
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-ink-mute">
                    <th className="pb-2 font-medium">Model</th>
                    <th className="pb-2 font-medium">Queries</th>
                    <th className="pb-2 text-right font-medium">Avg / query</th>
                    <th className="pb-2 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {byModel.map((m) => (
                    <tr key={m.model_key} className="border-t border-border">
                      <td className="py-2 font-mono text-ink">{m.model_key}</td>
                      <td className="py-2 text-ink-soft">{m.n_queries}</td>
                      <td className="py-2 text-right font-mono text-ink-soft">
                        {usd(m.avg_cost_usd, 5)}
                      </td>
                      <td className="py-2 text-right font-mono text-ink">
                        {usd(m.total_cost_usd, 5)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>

          {/* ── recent queries ── */}
          <Card className="p-5">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
              Recent queries
            </h2>
            <div className="space-y-1.5">
              {recent.map((r) => (
                <div
                  key={r.query_id}
                  className="flex items-center gap-3 rounded-sm border border-border bg-surface px-3 py-2 text-sm"
                >
                  <span className="min-w-0 flex-1 truncate text-ink">
                    {r.question}
                  </span>
                  <span className="shrink-0 rounded-sm bg-surface-2 px-1.5 py-0.5 text-[11px] capitalize text-ink-soft">
                    {r.thinking_tier}
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-ink-mute">
                    {r.n_inference_calls} calls ·{" "}
                    {(r.total_latency_ms / 1000).toFixed(1)}s
                  </span>
                  <span className="shrink-0 font-mono text-xs text-ink">
                    {usd(r.total_cost_usd, 5)}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="px-4 py-3">
      <div className="font-display text-2xl font-semibold text-ink">
        {value}
      </div>
      <div className="text-xs text-ink-mute">{label}</div>
    </Card>
  );
}

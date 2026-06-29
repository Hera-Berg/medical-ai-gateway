"use client";

/**
 * Settings — the storage backend switcher (step 10).
 *
 * Shows the active backend, lets you switch between Local and AWS, and:
 *   • runs a readiness probe before allowing a switch (blocks switching into a
 *     misconfigured AWS state — the next upload would otherwise fail),
 *   • requires confirming the "fresh index, no migration" warning,
 *   • surfaces current storage stats (disk warning for Local, cost for AWS).
 *
 * The switch takes effect immediately (the backend resolves the active backend
 * per request) — no restart.
 */
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type StorageSettings,
  type StorageReadiness,
  type StorageStats,
} from "@/lib/api";
import { Button, Card, Spinner, cn } from "@/components/ui/primitives";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<StorageSettings | null>(null);
  const [stats, setStats] = useState<StorageStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // switch flow state
  const [pending, setPending] = useState<string | null>(null); // backend being switched to
  const [readiness, setReadiness] = useState<StorageReadiness | null>(null);
  const [checking, setChecking] = useState(false);
  const [switching, setSwitching] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, st] = await Promise.all([
        api.getStorageSettings(),
        api.storageStats().catch(() => null),
      ]);
      setSettings(s);
      setStats(st);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // when a target backend is chosen, probe readiness
  const beginSwitch = async (name: string) => {
    if (name === settings?.active) return;
    setPending(name);
    setReadiness(null);
    setError(null);
    setChecking(true);
    try {
      setReadiness(await api.storageReadiness(name));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  const confirmSwitch = async () => {
    if (!pending) return;
    setSwitching(true);
    setError(null);
    try {
      await api.switchStorageBackend(pending, true);
      setPending(null);
      setReadiness(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSwitching(false);
    }
  };

  const cancelSwitch = () => {
    setPending(null);
    setReadiness(null);
    setError(null);
  };

  return (
    <div className="max-w-3xl space-y-6">
      <header className="fade-up">
        <h1 className="font-display text-3xl font-semibold text-ink">Settings</h1>
        <p className="mt-1 text-ink-soft">
          Choose where uploaded files and vector data are stored.
        </p>
      </header>

      {error && (
        <div className="rounded-sm border border-[var(--danger)]/30 bg-[var(--warn-soft)] px-4 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      {loading || !settings ? (
        <div className="flex items-center gap-2 text-sm text-ink-mute">
          <Spinner /> Loading settings…
        </div>
      ) : (
        <>
          {/* ── backend options ── */}
          <Card className="p-5">
            <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-ink-mute">
              Storage backend
            </h2>
            <p className="mb-4 text-xs text-ink-mute">
              Switching does not migrate existing data — the new backend starts
              with a fresh index.
            </p>

            <div className="space-y-3">
              {settings.options.map((opt) => {
                const active = opt.name === settings.active;
                return (
                  <div
                    key={opt.name}
                    className={cn(
                      "rounded border p-4 transition-colors",
                      active
                        ? "border-brand bg-brand-soft"
                        : "border-border bg-surface"
                    )}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-ink">{opt.label}</span>
                          <span className="text-xs text-ink-mute">
                            — {opt.tagline}
                          </span>
                          {active && (
                            <span className="rounded-sm bg-brand px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
                              Active
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-ink-soft">
                          {opt.description}
                        </p>
                      </div>
                      {!active && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => beginSwitch(opt.name)}
                          disabled={checking || switching}
                        >
                          Switch
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* ── switch confirmation (with readiness) ── */}
          {pending && (
            <Card className="border-warn/40 p-5">
              <h2 className="mb-2 font-display text-lg text-ink">
                Switch to{" "}
                {settings.options.find((o) => o.name === pending)?.label}?
              </h2>

              {checking ? (
                <div className="flex items-center gap-2 text-sm text-ink-mute">
                  <Spinner /> Checking backend is reachable…
                </div>
              ) : readiness ? (
                <div
                  className={cn(
                    "mb-3 rounded-sm border px-3 py-2 text-sm",
                    readiness.ready
                      ? "border-ok/30 bg-[var(--brand-soft)] text-brand-ink"
                      : "border-[var(--danger)]/30 bg-[var(--warn-soft)] text-danger"
                  )}
                >
                  {readiness.ready ? "✓ " : "✗ "}
                  {readiness.detail}
                </div>
              ) : null}

              <div className="mb-4 rounded-sm border border-warn/30 bg-[var(--warn-soft)] px-3 py-2 text-sm text-warn">
                <strong>Fresh index.</strong> Switching storage backend will
                start a fresh index. Existing documents will not be migrated.
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={confirmSwitch}
                  disabled={switching || !readiness?.ready}
                >
                  {switching ? <Spinner /> : "Confirm switch"}
                </Button>
                <Button variant="ghost" onClick={cancelSwitch} disabled={switching}>
                  Cancel
                </Button>
              </div>
              {readiness && !readiness.ready && (
                <p className="mt-2 text-xs text-ink-mute">
                  This backend isn’t reachable, so the switch is blocked. Fix the
                  configuration and try again.
                </p>
              )}
            </Card>
          )}

          {/* ── current storage stats ── */}
          {stats && (
            <Card className="p-5">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-mute">
                Current storage ({stats.backend_name})
              </h2>
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-ink-mute">Total stored</dt>
                  <dd className="font-medium text-ink">
                    {formatBytes(stats.total_bytes)}
                  </dd>
                </div>
                {stats.disk_usage_percent != null && (
                  <div>
                    <dt className="text-ink-mute">Host disk used</dt>
                    <dd
                      className={cn(
                        "font-medium",
                        stats.disk_warning ? "text-warn" : "text-ink"
                      )}
                    >
                      {stats.disk_usage_percent}%
                      {stats.disk_warning && " ⚠"}
                    </dd>
                  </div>
                )}
                <div>
                  <dt className="text-ink-mute">Est. monthly cost</dt>
                  <dd className="font-medium text-ink">
                    ${stats.estimated_monthly_cost_usd.toFixed(2)}
                  </dd>
                </div>
              </dl>
              {stats.disk_warning && (
                <p className="mt-3 rounded-sm border border-warn/30 bg-[var(--warn-soft)] px-3 py-2 text-xs text-warn">
                  Host disk usage is above 80%. Local storage is not recommended
                  for large datasets — consider AWS storage.
                </p>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}

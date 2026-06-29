"use client";

/**
 * ScatterPlot — renders the server-computed PCA 2D coordinates as an SVG scatter.
 * Each point is a chunk; hovering shows its text + page. Coordinates come
 * pre-projected from the backend (server-side PCA), so this component is purely
 * presentational: it normalises the coords into the viewBox and draws.
 *
 * SVG (not canvas) is deliberate at this scale (hundreds–few thousand points):
 * each point stays a real DOM node so hover/tooltip is trivial and crisp. For
 * tens of thousands we'd switch to canvas/WebGL — noted, not needed now.
 */
import { useMemo, useState } from "react";
import type { ScatterResult } from "@/lib/api";

const W = 720;
const H = 460;
const PAD = 28;

export function ScatterPlot({
  data,
  accent,
}: {
  data: ScatterResult;
  accent: string; // CSS var for the corpus colour
}) {
  const [hover, setHover] = useState<number | null>(null);

  const { norm, xExtent, yExtent } = useMemo(() => {
    const xs = data.points.map((p) => p.x);
    const ys = data.points.map((p) => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const spanX = maxX - minX || 1;
    const spanY = maxY - minY || 1;
    const norm = data.points.map((p) => ({
      cx: PAD + ((p.x - minX) / spanX) * (W - 2 * PAD),
      // invert y so positive is up, visually conventional
      cy: H - (PAD + ((p.y - minY) / spanY) * (H - 2 * PAD)),
    }));
    return { norm, xExtent: [minX, maxX], yExtent: [minY, maxY] };
  }, [data]);

  if (data.points.length === 0) {
    return (
      <div className="flex h-[460px] items-center justify-center text-sm text-ink-mute">
        No vectors to plot — ingest documents into this collection first.
      </div>
    );
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full rounded border border-border bg-surface"
        style={{ maxHeight: 480 }}
      >
        {/* faint axes cross at origin-ish center */}
        <rect x={0} y={0} width={W} height={H} fill="transparent" />
        {norm.map((n, i) => {
          const active = hover === i;
          return (
            <circle
              key={i}
              cx={n.cx}
              cy={n.cy}
              r={active ? 6 : 3.2}
              fill={`var(${accent})`}
              fillOpacity={active ? 1 : 0.55}
              stroke={active ? "white" : "none"}
              strokeWidth={active ? 1.5 : 0}
              style={{ transition: "r .08s, fill-opacity .08s", cursor: "crosshair" }}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((h) => (h === i ? null : h))}
            />
          );
        })}
      </svg>

      {/* hover tooltip */}
      {hover !== null && data.points[hover] && (
        <div className="pointer-events-none absolute left-3 top-3 max-w-md rounded border border-border bg-surface/95 p-3 text-xs shadow-md backdrop-blur">
          <div className="mb-1 font-medium text-ink-soft">
            {data.points[hover].filename}
            {data.points[hover].page_number != null && (
              <span className="text-ink-mute">
                {" "}
                · p.{data.points[hover].page_number}
              </span>
            )}
          </div>
          <div className="line-clamp-4 text-ink">
            {data.points[hover].text || "(empty chunk)"}
          </div>
        </div>
      )}

      <div className="mt-2 flex items-center justify-between text-[11px] text-ink-mute">
        <span>
          {data.point_count} chunks · {data.method.toUpperCase()} projection to 2D
        </span>
        <span>hover a point to see its text</span>
      </div>
    </div>
  );
}

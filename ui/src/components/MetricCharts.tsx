// Small hand-made charts for the Metrics "More info" panels (no chart library, F3).
// Colour only carries meaning: caught/missed and the three statuses. Everything else is neutral.
import type { ReactNode } from "react";
import { Tip } from "./Tip";

const fmt = (n: number) => n.toLocaleString("en-US");
const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;

export interface Segment {
  key: string;
  label: string;
  value: number;
  cls: string;
  /** Short exact-value tooltip. */
  tip: string;
}

/** A stacked horizontal bar with a labelled legend underneath. */
export function StackedBar({ parts, height = "h-4", legend = true }: { parts: Segment[]; height?: string; legend?: boolean }) {
  const total = parts.reduce((a, p) => a + p.value, 0) || 1;
  return (
    <div>
      <div className={`flex ${height} w-full overflow-hidden rounded-full bg-bar-track`}>
        {parts.map((p) =>
          p.value > 0 ? (
            <Tip key={p.key} content={p.tip} className={`h-full ${p.cls}`} style={{ width: `${(p.value / total) * 100}%` }}>
              <span className="sr-only">{p.tip}</span>
            </Tip>
          ) : null,
        )}
      </div>
      {legend && (
      <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-[14px]">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-2">
            <span aria-hidden className={`h-2.5 w-2.5 rounded-[3px] ${p.cls}`} />
            <span className="text-ink-2">{p.label}</span>
            <span className="num font-medium text-ink">{fmt(p.value)}</span>
            <span className="num text-ink-3">({pct(p.value / total)})</span>
          </li>
        ))}
      </ul>
      )}
    </div>
  );
}

export interface BarRow {
  key: string;
  label: ReactNode;
  value: number;
  max: number;
  display: string;
  sub?: string;
  weak?: boolean;
  tip: string;
}

/**
 * Labelled horizontal bars, one per row: label · bar · value · muted sub.
 * Units live once in `headers` (e.g. "Median, ms"), not on every value.
 */
export function BarList({
  rows,
  headers,
  labelWidth = "minmax(160px, 260px)",
}: {
  rows: BarRow[];
  headers?: { value: string; sub?: string };
  labelWidth?: string;
}) {
  return (
    <div className="grid items-center gap-x-4 gap-y-2 text-[14px]" style={{ gridTemplateColumns: `${labelWidth} minmax(80px,1fr) auto auto` }}>
      {headers && (
        <div className="contents text-[13px] font-medium text-ink-3">
          <span />
          <span />
          <span className="text-right">{headers.value}</span>
          <span className="text-right">{headers.sub ?? ""}</span>
        </div>
      )}
      {rows.map((r) => (
        <div key={r.key} className="contents">
          <span className="truncate text-ink">{r.label}</span>
          <span className="h-2.5 rounded-full bg-bar-track">
            <Tip content={r.tip} block className={`h-full rounded-full ${r.weak ? "bg-amber" : "bg-bar"}`} style={{ width: `${Math.max(1.5, (r.value / (r.max || 1)) * 100)}%` }}>
              <span className="sr-only">{r.tip}</span>
            </Tip>
          </span>
          <span className={`num text-right ${r.weak ? "font-semibold text-amber" : "font-medium text-ink"}`}>{r.display}</span>
          <span className="num text-right text-ink-3">{r.sub ?? ""}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Recall vs escalation rate: the trade-off points as a tiny line chart,
 * with the current operating point highlighted.
 */
export function TradeoffChart({
  rows,
  current,
}: {
  rows: { target_recall: number; escalation_rate: number }[];
  current?: { recall: number; rate: number };
}) {
  const W = 300;
  const H = 150;
  const pad = { l: 40, r: 12, t: 12, b: 30 };
  const pts = [...rows].sort((a, b) => a.target_recall - b.target_recall);
  const xs = [...pts.map((p) => p.target_recall), current?.recall ?? 0.9];
  const xMin = Math.min(0.75, ...xs) - 0.01;
  const xMax = Math.max(1, ...xs);
  const yMax = Math.max(0.5, ...pts.map((p) => p.escalation_rate), current?.rate ?? 0) * 1.1;
  const x = (v: number) => pad.l + ((v - xMin) / (xMax - xMin)) * (W - pad.l - pad.r);
  const y = (v: number) => H - pad.b - (v / yMax) * (H - pad.t - pad.b);
  const yTicks = [0, 0.25, 0.5].filter((t) => t <= yMax);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[340px]" role="img" aria-label="Escalation rate needed for each recall target">
      {yTicks.map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--line)" />
          <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="num" fontSize="11" fill="var(--ink-3)">
            {pct(t)}
          </text>
        </g>
      ))}
      <polyline
        fill="none"
        stroke="var(--ink-3)"
        strokeWidth="1.5"
        points={pts.map((p) => `${x(p.target_recall)},${y(p.escalation_rate)}`).join(" ")}
      />
      {pts.map((p) => (
        <g key={p.target_recall}>
          <circle cx={x(p.target_recall)} cy={y(p.escalation_rate)} r="3.5" fill="var(--surface)" stroke="var(--ink-2)" strokeWidth="1.5">
            <title>{`${pct(p.target_recall)} recall → ${pct(p.escalation_rate)} of tickets escalated`}</title>
          </circle>
          <text x={x(p.target_recall)} y={H - 10} textAnchor="middle" className="num" fontSize="11" fill="var(--ink-3)">
            {pct(p.target_recall)}
          </text>
        </g>
      ))}
      {current && (
        <g>
          <circle cx={x(current.recall)} cy={y(current.rate)} r="5" fill="var(--accent)">
            <title>{`Current setting: ${pct(current.recall, 1)} recall, ${pct(current.rate)} escalated`}</title>
          </circle>
          <text x={x(current.recall)} y={y(current.rate) - 9} textAnchor="middle" fontSize="11" fill="var(--accent)" fontWeight="600">
            now
          </text>
        </g>
      )}
    </svg>
  );
}

/** A 0…max scale with labelled markers (latency p50/p95). */
export function ScaleMarkers({ max, marks }: { max: number; marks: { label: string; value: number; display: string }[] }) {
  return (
    <div className="relative mt-6 mb-8 h-2 rounded-full bg-bar-track">
      {marks.map((m) => {
        const left = `${Math.min(100, (m.value / max) * 100)}%`;
        return (
          <span key={m.label} className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left }}>
            <span className="block h-5 w-[2px] rounded-full bg-ink" />
            <span className="num absolute top-6 left-1/2 -translate-x-1/2 text-[13px] whitespace-nowrap text-ink">
              <span className="font-semibold">{m.label}</span> {m.display}
            </span>
          </span>
        );
      })}
      <span className="num absolute -top-6 left-0 text-[12.5px] text-ink-3">0 s</span>
    </div>
  );
}

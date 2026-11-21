import { Fragment } from "react";
import { confidenceBand, fmtScore, thresholdsOf } from "../lib/labels";
import type { LabelPrediction, TriageResponse } from "../types/triage";
import { PriorityLabel } from "./PriorityLabel";
import { Section } from "./Section";

const HEADS = [
  ["type", "Type"],
  ["queue", "Queue"],
  ["priority", "Priority"],
] as const;

/**
 * All three rows share ONE grid, so bars have the same width, scale and tick position at
 * every viewport width (C4, review #1).
 */
export function Classification({ res }: { res: TriageResponse }) {
  const { t } = thresholdsOf(res);
  return (
    <Section
      label="Classification"
      meta={
        <span className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-3 w-[2px] bg-ink" /> gate threshold {fmtScore(t.confidence)}
        </span>
      }
    >
      <div className="grid grid-cols-[64px_minmax(150px,1fr)_minmax(100px,1.3fr)_44px_84px] items-center gap-x-3 gap-y-3 px-5 py-4">
        {HEADS.map(([key, name]) => (
          <Row key={key} name={name} head={key} p={res.classification[key]} threshold={t.confidence} />
        ))}
      </div>
    </Section>
  );
}

function Row({ name, head, p, threshold }: { name: string; head: string; p: LabelPrediction; threshold: number }) {
  const band = confidenceBand(p.confidence, threshold);
  const low = band === "Low";
  const alt = p.alternatives?.[0];
  return (
    <Fragment>
      <span className="text-[13px] text-ink-3">{name}</span>
      <span className="min-w-0">
        <span className="block text-[15px] leading-snug font-semibold break-words" title={p.label}>
          {head === "priority" ? <PriorityLabel label={p.label} /> : p.label}
        </span>
        {alt && (
          <span className="num block text-[11.5px] break-words text-ink-3" title={`alternative ${alt.label} ${fmtScore(alt.confidence)}`}>
            alt {alt.label} {fmtScore(alt.confidence)}
          </span>
        )}
      </span>
      <ConfidenceBar value={p.confidence} threshold={threshold} low={low} />
      <span className={`num text-right text-[14px] ${low ? "font-semibold text-amber" : "font-medium text-ink"}`}>{fmtScore(p.confidence)}</span>
      <span className={`text-[13px] ${low ? "font-semibold text-amber" : "text-ink-2"}`}>
        {band}
        {low && <span className="num ml-1 text-[12px] font-normal">&lt; {fmtScore(threshold)}</span>}
      </span>
    </Fragment>
  );
}

/** Identical for all three heads (C4): same height, scale, tick and number format. */
function ConfidenceBar({ value, threshold, low }: { value: number; threshold: number; low: boolean }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div
      className="relative h-2.5 rounded-full bg-bar-track"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={value}
      aria-label={`confidence ${fmtScore(value)}, threshold ${fmtScore(threshold)}`}
    >
      <div className={`h-full rounded-full ${low ? "bg-amber" : "bg-bar"}`} style={{ width: `${pct}%` }} />
      <div
        className="absolute -top-1 -bottom-1 w-[2px] rounded-full bg-ink"
        style={{ left: `calc(${threshold * 100}% - 1px)` }}
        title={`gate threshold ${fmtScore(threshold)}`}
      />
    </div>
  );
}

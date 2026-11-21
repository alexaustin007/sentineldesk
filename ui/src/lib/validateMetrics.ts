// Light runtime check of metrics.json (no library, F3; no runtime imports so node can test it).
import type { HeadName, Metrics } from "../types/metrics";

export class MetricsError extends Error {
  code = "BAD_METRICS";
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- untrusted JSON, narrowed below
type Obj = Record<string, any>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const HEADS: HeadName[] = ["type", "queue", "priority"];

/** Throws MetricsError listing every bad required path; drops malformed optional parts. */
export function parseMetrics(raw: unknown): Metrics {
  if (!isObj(raw)) throw new MetricsError("metrics.json is not a JSON object");
  const bad: string[] = [];
  for (const h of HEADS) {
    const m = raw.heads?.[h];
    const p = `heads.${h}`;
    if (!isObj(m)) {
      bad.push(p);
      continue;
    }
    if (!isNum(m.macro_f1)) bad.push(`${p}.macro_f1`);
    const n = Array.isArray(m.labels) && m.labels.every((l: unknown) => typeof l === "string") ? m.labels.length : -1;
    if (n < 1) bad.push(`${p}.labels`);
    if (!Array.isArray(m.per_class) || !m.per_class.every((c: Obj) => typeof c?.label === "string" && isNum(c.f1) && isNum(c.support)))
      bad.push(`${p}.per_class`);
    const square =
      Array.isArray(m.confusion) && m.confusion.length === n && m.confusion.every((r: unknown) => Array.isArray(r) && r.length === n && r.every(isNum));
    if (!square) bad.push(`${p}.confusion (must be ${n > 0 ? `${n}×${n}` : "square"}, rows = true, cols = predicted)`);
  }
  if (!isNum(raw.high_priority_incident_recall)) bad.push("high_priority_incident_recall");
  if (bad.length) throw new MetricsError(`metrics.json missing or invalid: ${bad.join(", ")}`);

  const pipe = isObj(raw.pipeline) ? raw.pipeline : null;
  const hpi = raw.high_priority_incident;
  const rate = (v: unknown) => (isNum(v) ? v : null);
  const dq = raw.drafts;
  const drafts =
    isObj(dq) && [dq.citations_valid_rate, dq.language_match_rate, dq.removed_claims_rate].some(isNum)
      ? { citations_valid_rate: rate(dq.citations_valid_rate), language_match_rate: rate(dq.language_match_rate), removed_claims_rate: rate(dq.removed_claims_rate) }
      : null;
  const heads = Object.fromEntries(
    HEADS.map((h) => {
      const m = raw.heads[h];
      const l = m.macro_f1_by_language;
      return [
        h,
        {
          ...m,
          calibration_error: isNum(m.calibration_error) ? m.calibration_error : undefined,
          macro_f1_by_language: isObj(l) && isNum(l.en) && isNum(l.de) ? { en: l.en, de: l.de } : undefined,
        },
      ];
    }),
  ) as Metrics["heads"];
  const optNum = (v: unknown) => (isNum(v) ? v : undefined);
  const optStr = (v: unknown) => (typeof v === "string" ? v : null);
  /** { key: number } with non-numbers dropped; null when nothing usable is left. */
  const numMap = (v: unknown) => {
    if (!isObj(v)) return null;
    const out = Object.fromEntries(Object.entries(v).filter(([, n]) => isNum(n))) as Record<string, number>;
    return Object.keys(out).length ? out : null;
  };
  return {
    ...(raw as unknown as Metrics),
    heads,
    calibration_error: isNum(raw.calibration_error) ? raw.calibration_error : undefined,
    drafts,
    high_priority_incident:
      isObj(hpi) && isNum(hpi.caught) && isNum(hpi.total) && hpi.total > 0
        ? { caught: hpi.caught, total: hpi.total, escalation_rate: optNum(hpi.escalation_rate) }
        : null,
    escalation_tradeoff: Array.isArray(raw.escalation_tradeoff)
      ? raw.escalation_tradeoff
          .filter((r: Obj) => isNum(r?.target_recall) && isNum(r?.escalation_rate))
          .map((r: Obj) => ({
            target_recall: r.target_recall,
            escalation_rate: r.escalation_rate,
            precision: optNum(r.precision),
            tickets_escalated: optNum(r.tickets_escalated),
          }))
      : [],
    split: isObj(raw.split) ? raw.split : undefined,
    pipeline: (pipe && {
      status_mix: isObj(pipe.status_mix) && ["auto_draft", "human_review", "escalate"].every((k) => isNum(pipe.status_mix[k])) ? pipe.status_mix : null,
      latency_ms: isObj(pipe.latency_ms) && isNum(pipe.latency_ms.p50) && isNum(pipe.latency_ms.p95) ? pipe.latency_ms : null,
      stage_latency_ms: numMap(pipe.stage_latency_ms),
      avg_cost_usd: isNum(pipe.avg_cost_usd) ? pipe.avg_cost_usd : null,
      cost_breakdown_usd: numMap(pipe.cost_breakdown_usd),
      cost_basis: optStr(pipe.cost_basis),
      tickets: optNum(pipe.tickets) ?? null,
    }) as Metrics["pipeline"],
  };
}

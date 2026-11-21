// Mirrors contracts/metrics.example.json (documented in docs/ui-specs/metrics.build.md).
// Written by the eval script; the UI only reads it.

export type HeadName = "type" | "queue" | "priority";
export const HEAD_NAMES: HeadName[] = ["type", "queue", "priority"];

export interface ClassMetrics {
  label: string;
  precision: number;
  recall: number;
  f1: number;
  support: number;
}

export interface HeadMetrics {
  macro_f1: number;
  accuracy?: number;
  labels: string[];
  per_class: ClassMetrics[];
  /** rows = true label, cols = predicted label, both in `labels` order */
  confusion: number[][];
}

export interface Metrics {
  /** true in the bundled example; the UI shows a "sample data" notice. */
  sample?: boolean;
  generated_at?: string;
  model?: string;
  dataset?: string;
  split?: { train?: number; knowledge_base?: number; holdout?: number; leakage_check?: string; leakage_detail?: string };
  heads: Record<HeadName, HeadMetrics>;
  high_priority_incident_recall: number;
  /** Counts behind the recall (holdout tickets with priority=high AND type=Incident) and the escalation rate at this operating point. */
  high_priority_incident?: { caught: number; total: number; escalation_rate?: number } | null;
  escalation_tradeoff?: TradeoffRow[];
  pipeline?: {
    status_mix?: { auto_draft: number; human_review: number; escalate: number } | null;
    latency_ms?: { p50: number; p95: number } | null;
    /** Median ms per pipeline stage (PR #5 stage keys), over the tickets where that stage ran. */
    stage_latency_ms?: Record<string, number> | null;
    avg_cost_usd?: number | null;
    /** Average USD per ticket by LLM stage; sums to avg_cost_usd. */
    cost_breakdown_usd?: Record<string, number> | null;
    /** How avg_cost_usd was estimated. */
    cost_basis?: string | null;
    /** Tickets the pipeline stats were measured on. */
    tickets?: number | null;
  } | null;
}

export interface TradeoffRow {
  target_recall: number;
  escalation_rate: number;
  /** Share of escalated tickets that really are high-priority incidents, at this recall. */
  precision?: number;
  /** Absolute number of holdout tickets escalated at this recall. */
  tickets_escalated?: number;
}

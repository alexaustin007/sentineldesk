import type { EscalationStatus, EscalationThresholds, TriageResponse } from "../types/triage";

export const DEFAULT_THRESHOLDS: EscalationThresholds = { confidence: 0.6, similarity: 0.55 };
export const HIGH_BAND = 0.85;
export const DUPLICATE_SIMILARITY = 0.9;

/** Missing or unknown status → "escalate" (fail safe, UI_WORKFLOW §3.1). */
export function normalizeStatus(status: unknown): EscalationStatus {
  return status === "auto_draft" ? "auto_draft" : "escalate";
}

export const STATUS_TEXT: Record<EscalationStatus, string> = {
  auto_draft: "Auto-Draft Ready",
  escalate: "Escalate to On-Call Engineer",
};

export function thresholdsOf(r: TriageResponse): { t: EscalationThresholds; fallback: boolean } {
  const t = r.escalation?.thresholds;
  if (t && typeof t.confidence === "number" && typeof t.similarity === "number") return { t, fallback: false };
  return { t: DEFAULT_THRESHOLDS, fallback: true };
}

export type Band = "Low" | "Medium" | "High";
export function confidenceBand(c: number, threshold: number): Band {
  if (c < threshold) return "Low";
  if (c >= HIGH_BAND) return "High";
  return "Medium";
}

/** Only these three priorities get colour; anything else is neutral and never treated as high. */
export type PriorityTone = "high" | "medium" | "low" | "neutral";
export function priorityTone(label: string | null | undefined): PriorityTone {
  return label === "high" || label === "medium" || label === "low" ? label : "neutral";
}

export function langCode(l: string | null | undefined): string {
  return l ? l.toUpperCase() : "—";
}

export function fmtScore(n: number): string {
  return n.toFixed(2);
}

export function fmtSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(2)} s`;
}

export function fmtMs(ms: number): string {
  return `${Math.round(ms).toLocaleString("en-US").replace(/,/g, " ")} ms`;
}

export function topSimilarity(r: TriageResponse): number | null {
  if (!r.precedents?.length) return null;
  return Math.max(...r.precedents.map((p) => p.similarity));
}

export function lowestConfidence(r: TriageResponse): { head: string; value: number } {
  const heads = ["type", "queue", "priority"] as const;
  return heads
    .map((h) => ({ head: h, value: r.classification[h].confidence }))
    .reduce((a, b) => (b.value < a.value ? b : a));
}

const hasReason = (r: TriageResponse, code: string) => r.escalation?.reasons?.some((x) => x.code === code) ?? false;

export interface GateCheck {
  code: string;
  label: string;
  pass: boolean;
  value: string;
}

/**
 * The five gate checks, worked out client-side from the response + thresholds.
 * A check fails if the computed rule fails OR the backend sent that reason code,
 * so the checklist never shows ✓ for something the gate escalated on.
 */
export function gateChecks(r: TriageResponse): GateCheck[] {
  const { t } = thresholdsOf(r);
  const c = r.classification;
  const low = lowestConfidence(r);
  const top = topSimilarity(r);
  const g = r.guardrails;
  const hpi = c.priority.label === "high" && c.type.label === "Incident";
  return [
    {
      code: "HIGH_PRIORITY_INCIDENT",
      // Wireframe wording when it fires; phrased as the passing condition otherwise.
      label: hpi || hasReason(r, "HIGH_PRIORITY_INCIDENT") ? "high priority + Incident" : "not a high-priority Incident",
      pass: !hpi && !hasReason(r, "HIGH_PRIORITY_INCIDENT"),
      value: `priority=${c.priority.label}, ${c.type.label}`,
    },
    {
      code: "LOW_CONFIDENCE",
      label: `confidence ≥ ${fmtScore(t.confidence)}`,
      pass: low.value >= t.confidence && !hasReason(r, "LOW_CONFIDENCE"),
      value: `lowest ${fmtScore(low.value)} (${low.head})`,
    },
    {
      code: "LOW_SIMILARITY",
      label: `precedent similarity ≥ ${fmtScore(t.similarity)}`,
      pass: top !== null && top >= t.similarity && !hasReason(r, "LOW_SIMILARITY"),
      value: top === null ? "no precedents" : `top ${fmtScore(top)}`,
    },
    {
      code: "UNSUPPORTED_REQUEST",
      label: "no unsupported request",
      pass: !g?.unsupported_request?.flagged && !hasReason(r, "UNSUPPORTED_REQUEST"),
      value: g?.unsupported_request?.evidence ? `“${g.unsupported_request.evidence}”` : g?.unsupported_request?.flagged ? "flagged" : "",
    },
    {
      code: "PROMPT_INJECTION",
      label: "no prompt injection",
      pass: !g?.prompt_injection?.flagged && !hasReason(r, "PROMPT_INJECTION"),
      value: g?.prompt_injection?.evidence ? `“${g.prompt_injection.evidence}”` : g?.prompt_injection?.flagged ? "flagged" : "",
    },
  ];
}

/** Operator-facing phrasing for each gate reason (banner line 2). Unknown codes show the backend message. */
export function reasonText(r: TriageResponse, code: string, message: string): string {
  const { t } = thresholdsOf(r);
  switch (code) {
    case "HIGH_PRIORITY_INCIDENT":
      return "High-priority Incident";
    case "LOW_CONFIDENCE": {
      const low = lowestConfidence(r);
      return `Low confidence (${low.head} ${fmtScore(low.value)} < ${fmtScore(t.confidence)})`;
    }
    case "LOW_SIMILARITY": {
      const top = topSimilarity(r);
      return top === null
        ? "No precedent: knowledge gap (no precedents retrieved)"
        : `No precedent: knowledge gap (top similarity ${fmtScore(top)} < ${fmtScore(t.similarity)})`;
    }
    case "UNSUPPORTED_REQUEST":
      return message && message.length <= 40 ? `Unsupported request (${message})` : "Unsupported request";
    case "PROMPT_INJECTION":
      return "Prompt injection detected";
    default:
      return message || code;
  }
}

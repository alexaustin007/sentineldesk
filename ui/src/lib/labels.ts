import type { EscalationStatus, EscalationThresholds, TriageResponse } from "../types/triage";

export const DEFAULT_THRESHOLDS: EscalationThresholds = { confidence: 0.55, similarity: 0.45, critical_incident_risk: null };
export const HIGH_BAND = 0.85;
export const DUPLICATE_SIMILARITY = 0.9;

/** Missing or unknown status → "escalate" (fail safe, UI_WORKFLOW §3.1). */
export function normalizeStatus(status: unknown): EscalationStatus {
  return status === "auto_draft" || status === "human_review" ? status : "escalate";
}

export const STATUS_TEXT: Record<EscalationStatus, string> = {
  auto_draft: "Auto-Draft Ready",
  human_review: "Needs Human Review",
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

/** "$0.0004"; null when missing or 0 (hidden). */
export function fmtCost(usd: number | undefined | null): string | null {
  if (!usd) return null;
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}

/** Display name for a backend stage key (free-form keys pass through). */
export function stageName(key: string): string {
  return key.replace(/_/g, " ");
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
const quote = (e: string | null | undefined) => (e ? `“${e}”` : "");

export interface GateCheck {
  code: string;
  label: string;
  pass: boolean;
  value: string;
}

/**
 * Gate checks, worked out client-side from the response + thresholds.
 * A check fails if the computed rule fails OR the backend sent that reason code,
 * so the checklist never shows ✓ for something the gate flagged.
 * Optional rows (risk, disagreement, language, verifier) appear only when they have data or fired.
 */
export function gateChecks(r: TriageResponse): GateCheck[] {
  const { t } = thresholdsOf(r);
  const c = r.classification;
  const low = lowestConfidence(r);
  const top = topSimilarity(r);
  const g = r.guardrails;
  const hpi = (c.priority.label === "high" && c.type.label === "Incident") || hasReason(r, "HIGH_PRIORITY_INCIDENT");

  const checks: GateCheck[] = [
    {
      code: "HIGH_PRIORITY_INCIDENT",
      // Wireframe wording when it fires; phrased as the passing condition otherwise.
      label: hpi ? "high priority + Incident" : "not a high-priority Incident",
      pass: !hpi,
      value: `priority=${c.priority.label}, ${c.type.label}`,
    },
  ];

  const risk = c.critical_incident_risk;
  if (risk != null) {
    const rt = t.critical_incident_risk;
    checks.push({
      code: "CRITICAL_INCIDENT_RISK",
      label: rt != null ? `critical incident risk < ${fmtScore(rt)}` : "critical incident risk",
      pass: (rt == null || risk < rt) && !hasReason(r, "CRITICAL_INCIDENT_RISK"),
      value: `risk ${fmtScore(risk)}`,
    });
  }

  const margins = (["type", "queue", "priority"] as const)
    .filter((h) => typeof c[h].margin === "number")
    .map((h) => ({ head: h, value: c[h].margin as number }));
  const minMargin = margins.length ? margins.reduce((a, b) => (b.value < a.value ? b : a)) : null;
  checks.push({
    code: "LOW_CONFIDENCE",
    label: `confidence ≥ ${fmtScore(t.confidence)}`,
    pass: low.value >= t.confidence && !hasReason(r, "LOW_CONFIDENCE") && !hasReason(r, "LOW_MARGIN"),
    value: `lowest ${fmtScore(low.value)} (${low.head})${minMargin ? ` · margin ${fmtScore(minMargin.value)} (${minMargin.head})` : ""}`,
  });

  checks.push({
    code: "LOW_SIMILARITY",
    label: `precedent similarity ≥ ${fmtScore(t.similarity)}`,
    pass: top !== null && top >= t.similarity && !hasReason(r, "LOW_SIMILARITY"),
    value: top === null ? "no precedents" : `top ${fmtScore(top)}`,
  });

  if (c.disagreements?.length) {
    checks.push({
      code: "DISAGREEMENT",
      label: `classifier vs precedents disagree on: ${c.disagreements.join(", ")}`,
      pass: false,
      value: r.route?.path && r.route.path !== "none" ? `route ${r.route.path}` : "",
    });
  }

  if (r.input?.language_supported === false || hasReason(r, "UNSUPPORTED_LANGUAGE")) {
    checks.push({
      code: "UNSUPPORTED_LANGUAGE",
      label: "supported language (EN/DE)",
      pass: false,
      value: langCode(r.input?.language_detected),
    });
  }

  checks.push({
    code: "UNSUPPORTED_REQUEST",
    label: "no unsupported request",
    pass: !g?.unsupported_request?.flagged && !hasReason(r, "UNSUPPORTED_REQUEST"),
    value: quote(g?.unsupported_request?.evidence) || (g?.unsupported_request?.flagged ? "flagged" : ""),
  });

  const signal = g?.prompt_injection?.evidence ?? g?.injection_signals?.[0];
  checks.push({
    code: "PROMPT_INJECTION",
    label: "no prompt injection",
    pass: !g?.prompt_injection?.flagged && !g?.injection_signals?.length && !hasReason(r, "PROMPT_INJECTION"),
    value: quote(signal) || (g?.prompt_injection?.flagged ? "flagged" : ""),
  });

  const issues = g?.verification_issues ?? [];
  const removed = g?.removed_claims ?? [];
  if (issues.length || removed.length || hasReason(r, "VERIFICATION_FAILED")) {
    checks.push({
      code: "VERIFICATION_FAILED",
      label: "verifier found no unsupported claims",
      pass: false,
      value: [removed.length ? `${removed.length} removed` : "", issues.length ? `${issues.length} issue${issues.length === 1 ? "" : "s"}` : ""]
        .filter(Boolean)
        .join(" · "),
    });
  }
  return checks;
}

/** Small tag shown before a reason message. Messages are always rendered verbatim; unknown/OTHER/missing code → no tag. */
export function reasonTag(code: string | undefined): string | null {
  switch (code) {
    case "HIGH_PRIORITY_INCIDENT":
      return "incident";
    case "CRITICAL_INCIDENT_RISK":
      return "critical risk";
    case "LOW_CONFIDENCE":
      return "low confidence";
    case "LOW_MARGIN":
      return "low margin";
    case "LOW_SIMILARITY":
      return "knowledge gap";
    case "UNSUPPORTED_REQUEST":
      return "unsupported";
    case "UNSUPPORTED_LANGUAGE":
      return "language";
    case "PROMPT_INJECTION":
      return "injection";
    case "VERIFICATION_FAILED":
      return "verifier";
    default:
      return null;
  }
}

// Mirrors contracts/triage_response.example.json (UI_WORKFLOW §3, revised 2026-11-21 for PR #5).
// Label fields are typed as `string` on purpose: the UI must print whatever
// the backend sends (queue verbatim, unknown priority → neutral grey).

export type Language = "en" | "de";

export interface TriageRequest {
  subject: string | null;
  body: string;
}

export interface LabelAlternative {
  label: string;
  confidence: number;
}

export interface LabelPrediction {
  label: string;
  confidence: number;
  /** Top minus second probability (Ivy's plan). */
  margin?: number;
  alternatives?: LabelAlternative[];
}

export interface Classification {
  type: LabelPrediction;
  queue: LabelPrediction;
  priority: LabelPrediction;
  /** Dedicated risk score 0–1, or null until it's wired in. */
  critical_incident_risk: number | null;
  /** Heads where classifier and precedent vote disagree, e.g. "queue". */
  disagreements: string[];
}

export type EscalationStatus = "auto_draft" | "human_review" | "escalate";

export type ReasonCode =
  | "HIGH_PRIORITY_INCIDENT"
  | "CRITICAL_INCIDENT_RISK"
  | "LOW_CONFIDENCE"
  | "LOW_MARGIN"
  | "LOW_SIMILARITY"
  | "UNSUPPORTED_REQUEST"
  | "UNSUPPORTED_LANGUAGE"
  | "PROMPT_INJECTION"
  | "VERIFICATION_FAILED"
  | "OTHER";

export interface EscalationReason {
  /** Best-effort tag; drives icons and the Why? checklist only. */
  code?: ReasonCode | string;
  /** Human sentence from the backend. Always rendered as given. */
  message: string;
}

export interface EscalationThresholds {
  confidence: number;
  similarity: number;
  critical_incident_risk?: number | null;
}

export interface Escalation {
  /** Missing or unknown values are treated as "escalate" (fail safe). */
  status?: EscalationStatus | string | null;
  reasons: EscalationReason[];
  thresholds?: EscalationThresholds;
}

export type RoutePath = "fast" | "deep" | "none";

export interface Route {
  path: RoutePath | string;
  reasons: string[];
}

export interface GuardrailFlag {
  flagged: boolean;
  evidence: string | null;
}

export interface Guardrails {
  prompt_injection: GuardrailFlag;
  unsupported_request: GuardrailFlag;
  injection_signals: string[];
  /** Draft sentences the verifier deleted (unsupported promises). Shown under the draft. */
  removed_claims: string[];
  verification_issues: string[];
  citations_valid: boolean;
}

export interface Precedent {
  ticket_id: string;
  similarity: number;
  /** May be missing until PR #5 exports it. */
  language?: Language | string;
  /** May be missing until PR #5 exports it. */
  subject?: string;
  type: string;
  queue: string;
  priority: string;
  answer_snippet: string;
  /** The past customer message (optional). */
  body?: string;
  /** The full resolution (optional; falls back to answer_snippet). */
  answer?: string;
}

export interface Draft {
  language: Language | string;
  text: string;
  citations: string[];
}

/** `total` plus free-form stage keys; stages that didn't run are omitted. */
export interface Latency {
  total: number;
  [stage: string]: number | undefined;
}

export interface Usage {
  total_tokens: number;
  estimated_cost_usd: number;
}

export interface TriageInput {
  subject: string | null;
  body: string;
  language_detected: Language | string;
  /** false for anything but EN/DE (goes to human review). */
  language_supported: boolean;
  /** e.g. { email: 1, phone: 1 }; {} if none. */
  pii_counts: Record<string, number>;
}

export interface TriageResponse {
  request_id: string;
  input: TriageInput;
  classification: Classification;
  escalation: Escalation;
  route: Route;
  guardrails: Guardrails;
  precedents: Precedent[];
  draft: Draft | null;
  latency_ms: Latency;
  usage?: Usage;
}

export interface TriageErrorBody {
  error: { code: string; message: string };
}

/** PR #5 stage keys, in pipeline order. */
export const PIPELINE_STAGES = ["guardrails", "classifier", "retrieval", "adversarial_review", "draft_reply", "verification"] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

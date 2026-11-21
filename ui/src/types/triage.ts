// Mirrors contracts/triage_response.example.json (UI_WORKFLOW §3).
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
  alternatives?: LabelAlternative[];
}

export interface Classification {
  type: LabelPrediction;
  queue: LabelPrediction;
  priority: LabelPrediction;
}

export type EscalationStatus = "auto_draft" | "escalate";

export type ReasonCode =
  | "HIGH_PRIORITY_INCIDENT"
  | "LOW_CONFIDENCE"
  | "LOW_SIMILARITY"
  | "UNSUPPORTED_REQUEST"
  | "PROMPT_INJECTION";

export interface EscalationReason {
  code: ReasonCode | string;
  message: string;
}

export interface EscalationThresholds {
  confidence: number;
  similarity: number;
}

export interface Escalation {
  /** Missing or unknown values are treated as "escalate" (fail safe). */
  status?: EscalationStatus | string | null;
  reasons: EscalationReason[];
  thresholds?: EscalationThresholds;
}

export interface GuardrailFlag {
  flagged: boolean;
  evidence: string | null;
}

export interface Guardrails {
  prompt_injection: GuardrailFlag;
  unsupported_request: GuardrailFlag;
  citations_valid: boolean;
}

export interface Precedent {
  ticket_id: string;
  similarity: number;
  language: Language | string;
  subject: string;
  type: string;
  queue: string;
  priority: string;
  answer_snippet: string;
}

export interface Draft {
  language: Language | string;
  text: string;
  citations: string[];
}

export interface Latency {
  total: number;
  classify?: number;
  retrieve?: number;
  generate?: number;
  guardrails?: number;
}

export interface TriageInput {
  subject: string | null;
  body: string;
  language_detected: Language | string;
  pii_masked: string[];
}

export interface TriageResponse {
  request_id: string;
  input: TriageInput;
  classification: Classification;
  escalation: Escalation;
  guardrails: Guardrails;
  precedents: Precedent[];
  draft: Draft | null;
  latency_ms: Latency;
}

export interface TriageErrorBody {
  error: { code: string; message: string };
}

export const PIPELINE_STAGES = ["classify", "retrieve", "generate", "guardrails"] as const;
export type PipelineStage = (typeof PIPELINE_STAGES)[number];

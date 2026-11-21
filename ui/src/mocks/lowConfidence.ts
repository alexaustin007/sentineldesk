import type { TriageResponse } from "../types/triage";

// Not a sample chip (max 4, D1). Used on /dev/states for the low-confidence state
// (UI_WORKFLOW §7 case 6, "help it broke"), plus an unknown priority label and a missing status.
export const lowConfidence: TriageResponse = {
  request_id: "mock_low_confidence",
  input: { subject: null, body: "help it broke", language_detected: "en", pii_masked: [] },
  classification: {
    type: { label: "Problem", confidence: 0.48, alternatives: [{ label: "Incident", confidence: 0.39 }] },
    queue: { label: "Technical Support", confidence: 0.41, alternatives: [{ label: "IT Support", confidence: 0.33 }] },
    priority: { label: "critical", confidence: 0.57 },
  },
  escalation: {
    reasons: [{ code: "LOW_CONFIDENCE", message: "lowest 0.41 (queue) < 0.60" }],
    thresholds: { confidence: 0.6, similarity: 0.55 },
  },
  guardrails: {
    prompt_injection: { flagged: false, evidence: null },
    unsupported_request: { flagged: false, evidence: null },
    citations_valid: false,
  },
  precedents: [
    {
      ticket_id: "TKT-33021",
      similarity: 0.58,
      language: "en",
      subject: "App crashes on start",
      type: "Problem",
      queue: "Technical Support",
      priority: "medium",
      answer_snippet: "Cleared the local cache and reinstalled version 3.8.2; crash no longer reproduces.",
    },
  ],
  draft: {
    language: "en",
    text: "Thanks for reaching out. Could you tell us which product and what you were doing when it stopped working? In a similar case [TKT-33021] clearing the cache helped; see also [TKT-99999].",
    citations: ["TKT-33021", "TKT-99999"],
  },
  latency_ms: { total: 1310, classify: 30, retrieve: 101, generate: 1102 },
};

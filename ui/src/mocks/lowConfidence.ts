import type { TriageResponse } from "../types/triage";

// Not an example link (max 4, D1). Used on /dev/states for the low-confidence state
// (UI_WORKFLOW §7 case 6, "help it broke"), plus an unknown priority label, a missing status
// and an invalid citation.
export const lowConfidence: TriageResponse = {
  request_id: "mock_low_confidence",
  input: { subject: null, body: "help it broke", language_detected: "en", language_supported: true, pii_counts: {} },
  classification: {
    type: { label: "Problem", confidence: 0.48, margin: 0.09, alternatives: [{ label: "Incident", confidence: 0.39 }] },
    queue: { label: "Technical Support", confidence: 0.41, margin: 0.08, alternatives: [{ label: "IT Support", confidence: 0.33 }] },
    priority: { label: "critical", confidence: 0.52 },
    critical_incident_risk: null,
    disagreements: [],
  },
  escalation: {
    reasons: [{ code: "LOW_CONFIDENCE", message: "Classifier confidence too low on queue (0.41, needs 0.55)" }],
    thresholds: { confidence: 0.55, similarity: 0.45, critical_incident_risk: null },
  },
  route: { path: "fast", reasons: [] },
  guardrails: {
    prompt_injection: { flagged: false, evidence: null },
    unsupported_request: { flagged: false, evidence: null },
    injection_signals: [],
    removed_claims: [],
    verification_issues: [],
    citations_valid: false,
  },
  precedents: [
    {
      ticket_id: "TKT-33021",
      body: "The app crashes right after the splash screen since this morning.",
      answer: "Cleared the local cache and reinstalled version 3.8.2; crash no longer reproduces. A fix for the cache corruption ships in 3.8.3.",
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
  latency_ms: { total: 1310, guardrails: 6, classifier: 9, retrieval: 118, draft_reply: 1120 },
  usage: { total_tokens: 512, estimated_cost_usd: 0.0002 },
};

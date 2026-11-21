import type { TriageResponse } from "../types/triage";

// Wireframe C · sample chip "No subject". Body only, nothing similar in the KB.
export const knowledgeGap: TriageResponse = {
  request_id: "mock_knowledge_gap",
  input: {
    subject: null,
    body: "hi, does your scheduling tool have a native connector for our Epic Hyperspace install? we need two-way sync of appointment slots before go-live next month. who can set this up?",
    language_detected: "en",
    pii_masked: [],
  },
  classification: {
    type: { label: "Request", confidence: 0.79, alternatives: [{ label: "Change", confidence: 0.12 }] },
    queue: { label: "Sales and Pre-Sales", confidence: 0.66, alternatives: [{ label: "Product Support", confidence: 0.25 }] },
    priority: { label: "medium", confidence: 0.71, alternatives: [{ label: "low", confidence: 0.22 }] },
  },
  escalation: {
    status: "escalate",
    reasons: [{ code: "LOW_SIMILARITY", message: "top similarity 0.31 < 0.55" }],
    thresholds: { confidence: 0.6, similarity: 0.55 },
  },
  guardrails: {
    prompt_injection: { flagged: false, evidence: null },
    unsupported_request: { flagged: false, evidence: null },
    citations_valid: true,
  },
  precedents: [
    {
      ticket_id: "TKT-28104",
      similarity: 0.31,
      language: "en",
      subject: "Calendar export to Outlook",
      type: "Request",
      queue: "Product Support",
      priority: "low",
      answer_snippet: "Explained the ICS export under Settings → Calendar and the hourly refresh limit.",
    },
    {
      ticket_id: "TKT-15660",
      similarity: 0.27,
      language: "de",
      subject: "Schnittstelle zu SAP gewünscht",
      type: "Request",
      queue: "Sales and Pre-Sales",
      priority: "medium",
      answer_snippet: "An den Vertrieb weitergeleitet; eine SAP-Schnittstelle ist derzeit nicht im Produktumfang.",
    },
    {
      ticket_id: "TKT-09385",
      similarity: 0.22,
      language: "en",
      subject: "API rate limits for bulk import",
      type: "Problem",
      queue: "Technical Support",
      priority: "low",
      answer_snippet: "Raised the import batch limit to 500 rows and pointed to the bulk endpoint docs.",
    },
  ],
  draft: null,
  latency_ms: { total: 940, classify: 34, retrieve: 117, guardrails: 61 },
};

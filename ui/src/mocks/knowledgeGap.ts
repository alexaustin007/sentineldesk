import type { TriageResponse } from "../types/triage";

// Wireframe C · example "No subject". Body only, nothing similar in the KB.
// Under PR #5 this is human_review (amber), not escalate.
export const knowledgeGap: TriageResponse = {
  request_id: "mock_knowledge_gap",
  input: {
    subject: null,
    body: "hi, does your scheduling tool have a native connector for our Epic Hyperspace install? we need two-way sync of appointment slots before go-live next month. who can set this up?",
    language_detected: "en",
    language_supported: true,
    pii_counts: {},
  },
  classification: {
    type: { label: "Request", confidence: 0.79, margin: 0.67, alternatives: [{ label: "Change", confidence: 0.12 }] },
    queue: { label: "Sales and Pre-Sales", confidence: 0.66, margin: 0.41, alternatives: [{ label: "Product Support", confidence: 0.25 }] },
    priority: { label: "medium", confidence: 0.71, margin: 0.49, alternatives: [{ label: "low", confidence: 0.22 }] },
    critical_incident_risk: null,
    disagreements: [],
  },
  escalation: {
    status: "human_review",
    reasons: [{ code: "LOW_SIMILARITY", message: "No close historical precedent (top similarity 0.31, needs 0.45)" }],
    thresholds: { confidence: 0.55, similarity: 0.45, critical_incident_risk: null },
  },
  route: { path: "none", reasons: [] },
  guardrails: {
    prompt_injection: { flagged: false, evidence: null },
    unsupported_request: { flagged: false, evidence: null },
    injection_signals: [],
    removed_claims: [],
    verification_issues: [],
    citations_valid: true,
  },
  precedents: [
    {
      ticket_id: "TKT-28104",
      body: "Can I export my appointments to Outlook? I only see a download button.",
      answer: "Explained the ICS export under Settings → Calendar. Outlook refreshes subscribed calendars about once an hour, so changes are not instant.",
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
      body: "Wir möchten Termine automatisch mit SAP abgleichen. Gibt es dafür eine Schnittstelle?",
      answer: "An den Vertrieb weitergeleitet; eine SAP-Schnittstelle ist derzeit nicht im Produktumfang. Der Vertrieb meldet sich mit Optionen über die REST-API.",
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
  latency_ms: { total: 196, guardrails: 5, classifier: 10, retrieval: 171 },
  usage: { total_tokens: 0, estimated_cost_usd: 0 },
};

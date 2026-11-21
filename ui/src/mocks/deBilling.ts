import type { TriageResponse } from "../types/triage";

// Wireframe B · sample chip "DE billing". Auto-draft, German reply, likely duplicate.
export const deBilling: TriageResponse = {
  request_id: "mock_de_billing",
  input: {
    subject: "Doppelte Abbuchung im November",
    body: "Guten Tag, mir wurde das Monatsabo für November zweimal von der Kreditkarte abgebucht. Können Sie die zweite Buchung bitte prüfen und erstatten? Vielen Dank.",
    language_detected: "de",
    pii_masked: [],
  },
  classification: {
    type: { label: "Request", confidence: 0.88, alternatives: [{ label: "Problem", confidence: 0.09 }] },
    queue: { label: "Billing and Payments", confidence: 0.81, alternatives: [{ label: "Customer Service", confidence: 0.12 }] },
    priority: { label: "medium", confidence: 0.74, alternatives: [{ label: "low", confidence: 0.2 }] },
  },
  escalation: {
    status: "auto_draft",
    reasons: [],
    thresholds: { confidence: 0.6, similarity: 0.55 },
  },
  guardrails: {
    prompt_injection: { flagged: false, evidence: null },
    unsupported_request: { flagged: false, evidence: null },
    citations_valid: true,
  },
  precedents: [
    {
      ticket_id: "TKT-12093",
      similarity: 0.92,
      language: "de",
      subject: "Doppelte Abbuchung im Oktober",
      type: "Request",
      queue: "Billing and Payments",
      priority: "medium",
      answer_snippet:
        "Wir haben die doppelte Abbuchung bestätigt und die zweite Transaktion storniert. Die Gutschrift erscheint in 3–5 Werktagen auf Ihrer Karte.",
    },
    {
      ticket_id: "TKT-40766",
      similarity: 0.81,
      language: "en",
      subject: "Charged twice for subscription",
      type: "Request",
      queue: "Billing and Payments",
      priority: "medium",
      answer_snippet:
        "We confirmed the duplicate charge and reversed the second transaction. The refund appears on your statement within 3–5 business days.",
    },
    {
      ticket_id: "TKT-07731",
      similarity: 0.64,
      language: "de",
      subject: "Rechnung nicht erhalten",
      type: "Problem",
      queue: "Billing and Payments",
      priority: "low",
      answer_snippet: "Die Rechnung wurde erneut an die hinterlegte Adresse gesendet und ist zusätzlich im Kundenportal abrufbar.",
    },
  ],
  draft: {
    language: "de",
    text: "Guten Tag, vielen Dank für Ihre Nachricht. Wie in vergleichbaren Fällen [TKT-12093] prüfen wir die doppelte Abbuchung für November und stornieren die zweite Transaktion, sobald sie bestätigt ist. Die Gutschrift erscheint in der Regel innerhalb von 3–5 Werktagen auf Ihrer Karte [TKT-40766]. Mit freundlichen Grüßen, Ihr Support-Team",
    citations: ["TKT-12093", "TKT-40766"],
  },
  latency_ms: { total: 1620, classify: 31, retrieve: 104, generate: 1402, guardrails: 83 },
};

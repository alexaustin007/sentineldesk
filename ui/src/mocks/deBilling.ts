import type { TriageResponse } from "../types/triage";

// Wireframe B · example "German billing". Auto-draft, German reply, likely duplicate.
export const deBilling: TriageResponse = {
  request_id: "mock_de_billing",
  input: {
    subject: "Doppelte Abbuchung im November",
    body: "Guten Tag, mir wurde das Monatsabo für November zweimal von der Kreditkarte abgebucht. Können Sie die zweite Buchung bitte prüfen und erstatten? Vielen Dank.",
    language_detected: "de",
    language_supported: true,
    pii_counts: {},
  },
  classification: {
    type: { label: "Request", confidence: 0.88, margin: 0.79, alternatives: [{ label: "Problem", confidence: 0.09 }] },
    queue: { label: "Billing and Payments", confidence: 0.81, margin: 0.69, alternatives: [{ label: "Customer Service", confidence: 0.12 }] },
    priority: { label: "medium", confidence: 0.74, margin: 0.54, alternatives: [{ label: "low", confidence: 0.2 }] },
    critical_incident_risk: null,
    disagreements: [],
  },
  escalation: {
    status: "auto_draft",
    reasons: [],
    thresholds: { confidence: 0.55, similarity: 0.45, critical_incident_risk: null },
  },
  route: { path: "fast", reasons: ["classifier and precedents agree", "top similarity 0.92"] },
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
      ticket_id: "TKT-12093",
      body: "Hallo, mein Abo für Oktober wurde zweimal von meiner Kreditkarte abgebucht. Ich habe beide Buchungen in der Abrechnung gesehen. Bitte prüfen Sie das und erstatten Sie den doppelten Betrag.\n\nVielen Dank\nM. Keller",
      answer: "Guten Tag Frau Keller, wir haben die doppelte Abbuchung für Oktober bestätigt und die zweite Transaktion storniert. Die Gutschrift erscheint in 3–5 Werktagen auf Ihrer Karte. Die Ursache war ein Zahlungs-Retry nach einer kurzen Störung unseres Zahlungsanbieters; wir haben den Retry für Ihr Konto deaktiviert, damit das nicht erneut passiert. Mit freundlichen Grüßen, Ihr Support-Team",
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
      body: "Hi, I was charged twice for my monthly subscription this month. Both charges show on my bank statement on the same day. Can you refund one of them?",
      answer: "We confirmed the duplicate charge and reversed the second transaction. The refund appears on your statement within 3–5 business days, depending on your bank. No action is needed on your side; your subscription stays active.",
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
      body: "Ich habe für September keine Rechnung erhalten, obwohl der Betrag abgebucht wurde. Bitte senden Sie mir die Rechnung zu.",
      answer: "Die Rechnung wurde erneut an die hinterlegte Adresse gesendet und ist zusätzlich im Kundenportal unter Konto → Rechnungen abrufbar.",
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
  latency_ms: { total: 1620, guardrails: 7, classifier: 11, retrieval: 142, draft_reply: 1391, verification: 69 },
  usage: { total_tokens: 846, estimated_cost_usd: 0.0004 },
};

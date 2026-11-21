import type { TriageResponse } from "../types/triage";

// Wireframe E · /dev/states only (D1: at most 4 example links).
// human_review with a draft: deep route, classifier vs precedents disagree on queue,
// verifier removed one unsupported claim. One precedent lacks language/subject (PR #5 gap)
// and one reason has no code, to exercise both fallbacks.
export const humanReviewDeep: TriageResponse = {
  request_id: "mock_human_review_deep",
  input: {
    subject: "Locked out after SSO change and charged twice",
    body: "Since you switched us to the new SSO provider nobody on our team can get into the admin dashboard, and this month's invoice was charged twice. Please fix the login and refund the extra charge within 24 hours.",
    language_detected: "en",
    language_supported: true,
    pii_counts: { email: 1 },
  },
  classification: {
    type: { label: "Problem", confidence: 0.71, margin: 0.47, alternatives: [{ label: "Incident", confidence: 0.24 }] },
    queue: { label: "Technical Support", confidence: 0.58, margin: 0.08, alternatives: [{ label: "Billing and Payments", confidence: 0.5 }] },
    priority: { label: "medium", confidence: 0.66, margin: 0.38, alternatives: [{ label: "high", confidence: 0.28 }] },
    critical_incident_risk: 0.22,
    disagreements: ["queue"],
  },
  escalation: {
    status: "human_review",
    reasons: [
      { code: "OTHER", message: "Agents disagree on queue: classifier says Technical Support, precedent vote says Billing and Payments" },
      { message: "Verifier removed 1 unsupported claim from the draft" },
    ],
    thresholds: { confidence: 0.55, similarity: 0.45, critical_incident_risk: 0.6 },
  },
  route: { path: "deep", reasons: ["queue disagreement", "queue margin 0.08"] },
  guardrails: {
    prompt_injection: { flagged: false, evidence: null },
    unsupported_request: { flagged: false, evidence: null },
    injection_signals: [],
    removed_claims: ["We will refund 50 € within 24 hours."],
    verification_issues: ["refund amount and deadline are not supported by any precedent"],
    citations_valid: true,
  },
  precedents: [
    {
      ticket_id: "TKT-14470",
      body: "Since moving to the new identity provider, admins get stuck in a login loop on the dashboard. Regular users seem fine.",
      answer: "Re-registered the redirect URI with the new identity provider and cleared stale SAML sessions for the admin group. Admins could log in again immediately; we also added the new IdP certificate to the trust store so the loop does not return at the next rotation.",
      similarity: 0.74,
      language: "en",
      subject: "Admin login loops after IdP migration",
      type: "Problem",
      queue: "Technical Support",
      priority: "medium",
      answer_snippet: "Re-registered the redirect URI with the new identity provider and cleared stale SAML sessions; admins could log in again.",
    },
    {
      ticket_id: "TKT-27731",
      body: "We changed plans mid-month and were charged for both plans. Please refund the old one.",
      answer: "Billing confirmed the duplicate charge and issued a refund through the standard billing review (3–5 business days). The plan change itself was applied correctly.",
      similarity: 0.69,
      language: "en",
      subject: "Charged twice after plan change",
      type: "Request",
      queue: "Billing and Payments",
      priority: "medium",
      answer_snippet: "Billing confirmed the duplicate charge and issued a refund through the standard billing review.",
    },
    {
      ticket_id: "TKT-36002",
      similarity: 0.52,
      type: "Problem",
      queue: "Billing and Payments",
      priority: "low",
      answer_snippet: "Invoice re-issued after the account owner changed; duplicate line removed.",
    },
  ],
  draft: {
    language: "en",
    text: "Thank you for your message, and sorry for the trouble. In a similar case [TKT-14470] re-registering the login redirect with the new SSO provider restored admin access; our technical team is checking that now. We have also asked billing to review the duplicate charge, as in [TKT-27731].",
    citations: ["TKT-14470", "TKT-27731"],
  },
  latency_ms: { total: 3800, guardrails: 7, classifier: 10, retrieval: 153, adversarial_review: 1410, draft_reply: 1980, verification: 240 },
  usage: { total_tokens: 2140, estimated_cost_usd: 0.0021 },
};

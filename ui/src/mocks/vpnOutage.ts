import type { TriageResponse } from "../types/triage";

// Wireframe A · example "VPN outage". Mirrors contracts/triage_response.example.json:
// PR #5 pages on-call before any LLM call, so escalate comes back with draft: null.
export const vpnOutage: TriageResponse = {
  request_id: "mock_vpn_outage",
  input: {
    subject: "VPN down - telemedicine offline",
    body: "Since 07:40 our clinic VPN drops every connection. EMR integration and telemedicine sessions are failing for all staff. Please help urgently.",
    language_detected: "en",
    language_supported: true,
    pii_counts: {},
  },
  classification: {
    type: { label: "Incident", confidence: 0.91, margin: 0.85, alternatives: [{ label: "Problem", confidence: 0.06 }] },
    queue: { label: "Technical Support", confidence: 0.78, margin: 0.61, alternatives: [{ label: "IT Support", confidence: 0.17 }] },
    priority: { label: "high", confidence: 0.84, margin: 0.71, alternatives: [{ label: "medium", confidence: 0.13 }] },
    critical_incident_risk: null,
    disagreements: [],
  },
  escalation: {
    status: "escalate",
    reasons: [{ code: "HIGH_PRIORITY_INCIDENT", message: "High-priority Incident flagged by the classifier and 80% of the precedent vote" }],
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
      ticket_id: "TKT-01842",
      body: "From: it-ops@clinic.example\nSubject: VPN drops after update\n\nAfter last night's firmware update our site-to-site VPN drops every few minutes. Remote staff cannot reach internal systems and the clinic portal times out.\n\nWhat we tried so far:\n- restarted the gateway twice\n- re-imported the client profile on two laptops\n- checked the ISP status page (no outage reported)\n\nThe drops started at 06:10 and line up with the scheduled firmware push. Please advise whether we can roll back.",
      answer: "Rolled back the gateway firmware to 4.2.1 and reissued client certificates for all remote users. The tunnel has been stable for 24 hours. If drops return, please send the gateway log export and we will escalate to the network team.",
      similarity: 0.83,
      language: "en",
      subject: "VPN connection drops after firmware update",
      type: "Incident",
      queue: "Technical Support",
      priority: "high",
      answer_snippet:
        "Rolled back the gateway firmware to 4.2.1 and reissued client certificates. Connections stayed stable for 48 h; firmware 4.3 is on hold until the vendor patch.",
    },
    {
      ticket_id: "TKT-30517",
      body: "Seit heute Morgen bricht die VPN-Verbindung aller Außendienstmitarbeiter alle paar Minuten ab. Bitte dringend prüfen.",
      answer: "Wir haben die MTU-Einstellungen am Gateway angepasst und die Keepalive-Intervalle verkürzt. Die Verbindungen sind seitdem stabil. Bitte melden Sie sich, falls die Abbrüche erneut auftreten.",
      similarity: 0.76,
      language: "de",
      subject: "VPN-Verbindung bricht ständig ab",
      type: "Incident",
      queue: "IT Support",
      priority: "high",
      answer_snippet:
        "Wir haben die MTU-Einstellungen am Gateway auf 1400 angepasst und die Clients neu verbunden. Seitdem keine Abbrüche mehr.",
    },
  ],
  draft: null,
  latency_ms: { total: 182, guardrails: 6, classifier: 9, retrieval: 160 },
  usage: { total_tokens: 0, estimated_cost_usd: 0 },
};

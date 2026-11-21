import type { TriageResponse } from "../types/triage";

// Wireframe A · sample chip "VPN outage". Mirrors contracts/triage_response.example.json.
export const vpnOutage: TriageResponse = {
  request_id: "mock_vpn_outage",
  input: {
    subject: "VPN down - telemedicine offline",
    body: "Since 07:40 our clinic VPN drops every connection. EMR integration and telemedicine sessions are failing for all staff. Please help urgently.",
    language_detected: "en",
    pii_masked: [],
  },
  classification: {
    type: { label: "Incident", confidence: 0.91, alternatives: [{ label: "Problem", confidence: 0.06 }] },
    queue: { label: "Technical Support", confidence: 0.78, alternatives: [{ label: "IT Support", confidence: 0.17 }] },
    priority: { label: "high", confidence: 0.84, alternatives: [{ label: "medium", confidence: 0.13 }] },
  },
  escalation: {
    status: "escalate",
    reasons: [{ code: "HIGH_PRIORITY_INCIDENT", message: "priority=high and type=Incident" }],
    thresholds: { confidence: 0.6, similarity: 0.55 },
  },
  guardrails: {
    prompt_injection: { flagged: false, evidence: null },
    unsupported_request: { flagged: false, evidence: null },
    citations_valid: true,
  },
  precedents: [
    {
      ticket_id: "TKT-01842",
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
  draft: {
    language: "en",
    text: "Thank you for reporting this. We have escalated your VPN outage to our on-call engineer, who is looking at it now. In similar cases [TKT-01842], rolling back the gateway firmware and reissuing client certificates restored service; we will also check the gateway MTU settings [TKT-30517]. We will update you within 30 minutes.",
    citations: ["TKT-01842", "TKT-30517"],
  },
  latency_ms: { total: 2140, classify: 35, retrieve: 120, generate: 1890, guardrails: 95 },
};

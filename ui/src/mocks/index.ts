import type { TriageRequest, TriageResponse } from "../types/triage";
import { deBilling } from "./deBilling";
import { humanReviewDeep } from "./humanReviewDeep";
import { injection } from "./injection";
import { knowledgeGap } from "./knowledgeGap";
import { lowConfidence } from "./lowConfidence";
import { vpnOutage } from "./vpnOutage";

export { deBilling, humanReviewDeep, injection, knowledgeGap, lowConfidence, vpnOutage };

export interface Sample {
  id: string;
  label: string;
  request: TriageRequest;
  mock: TriageResponse;
}

// The four example tickets (D1: ≤4), shown as quiet links. Each fills the form and maps to one mock.
export const SAMPLES: Sample[] = [
  { id: "vpn", label: "VPN outage", mock: vpnOutage },
  { id: "de-billing", label: "German billing", mock: deBilling },
  { id: "injection", label: "Injection attempt", mock: injection },
  { id: "no-subject", label: "No subject", mock: knowledgeGap },
].map((s) => ({ ...s, request: { subject: s.mock.input.subject, body: s.mock.input.body } }));

/** Mock routing for text that is not a sample: crude keyword match, echoing the real input back. */
export function pickMock(req: TriageRequest): TriageResponse {
  const exact = SAMPLES.find((s) => s.request.body.trim() === req.body.trim());
  const base = exact?.mock ?? guess(`${req.subject ?? ""} ${req.body}`.toLowerCase());
  return { ...base, input: { ...base.input, subject: req.subject, body: req.body } };
}

function guess(text: string): TriageResponse {
  if (/ignore (all |any )?previous|system note|disregard/.test(text)) return injection;
  if (/[äöüß]|\b(und|ich|bitte|danke|nicht)\b/.test(text)) return deBilling;
  if (/vpn|outage|down|offline/.test(text)) return vpnOutage;
  if (/sso|locked out|charged twice|refund/.test(text)) return humanReviewDeep;
  if (text.trim().split(/\s+/).length < 5) return lowConfidence;
  return knowledgeGap;
}

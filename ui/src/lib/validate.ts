// Runtime check of the backend response (hand-written, no library: F3).
// No runtime imports, so `node ui/src/lib/validate.test.ts` can run it directly.
import type { EscalationReason, TriageResponse } from "../types/triage";

export class TriageError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- untrusted JSON, narrowed field by field below
type Obj = Record<string, any>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isStr = (v: unknown): v is string => typeof v === "string";
const strs = (v: unknown): string[] => (Array.isArray(v) ? v.filter(isStr) : []);
const clamp01 = (n: number) => Math.min(1, Math.max(0, n));
const HEADS = ["type", "queue", "priority"] as const;
const STATUSES = ["auto_draft", "human_review", "escalate"];
const bad = (msg: string) => new TriageError("BAD_RESPONSE", msg);

/** Throws BAD_RESPONSE listing every missing required path; normalizes everything else (fail safe). */
export function parseTriageResponse(raw: unknown): TriageResponse {
  if (isObj(raw) && "final_labels" in raw)
    throw bad("Backend returned PR #5's raw TriageResult; the API wrapper must convert it (docs/UI_WORKFLOW.md §3.2)");
  if (!isObj(raw)) throw bad("Backend response missing or invalid: (body is not a JSON object)");

  const missing: string[] = [];
  const c = isObj(raw.classification) ? raw.classification : {};
  for (const h of HEADS) {
    if (!isStr(c[h]?.label)) missing.push(`classification.${h}.label`);
    if (!isNum(c[h]?.confidence)) missing.push(`classification.${h}.confidence`);
  }
  if (!Array.isArray(raw.precedents)) missing.push("precedents");
  else
    raw.precedents.forEach((p: unknown, i: number) => {
      if (!isStr((p as Obj)?.ticket_id)) missing.push(`precedents[${i}].ticket_id`);
      if (!isNum((p as Obj)?.similarity)) missing.push(`precedents[${i}].similarity`);
    });
  if (!isNum(raw.latency_ms?.total)) missing.push("latency_ms.total");
  if (missing.length) throw bad(`Backend response missing or invalid: ${missing.join(", ")}`);

  const e = isObj(raw.escalation) ? raw.escalation : {};
  const reasons: EscalationReason[] = Array.isArray(e.reasons)
    ? e.reasons.filter((r: unknown) => isStr((r as Obj)?.message)).map((r: Obj) => ({ code: isStr(r.code) ? r.code : undefined, message: r.message }))
    : [];
  const known = STATUSES.includes(e.status);
  if (!known) reasons.unshift({ code: "OTHER", message: "Backend sent no escalation decision; treated as escalate" });
  const t = isObj(e.thresholds) ? e.thresholds : {};
  const g = isObj(raw.guardrails) ? raw.guardrails : {};
  const flag = (f: unknown) => ({ flagged: (f as Obj)?.flagged === true, evidence: isStr((f as Obj)?.evidence) ? (f as Obj).evidence : null });
  const inp = isObj(raw.input) ? raw.input : {};
  const d = raw.draft;

  return {
    ...(raw as unknown as TriageResponse),
    request_id: isStr(raw.request_id) ? raw.request_id : "",
    input: {
      subject: isStr(inp.subject) ? inp.subject : null,
      body: isStr(inp.body) ? inp.body : "",
      language_detected: isStr(inp.language_detected) ? inp.language_detected : "en",
      language_missing: !isStr(inp.language_detected) || undefined,
      language_supported: inp.language_supported !== false,
      pii_counts: isObj(inp.pii_counts) ? inp.pii_counts : {},
    },
    classification: {
      ...c,
      ...Object.fromEntries(HEADS.map((h) => [h, { ...c[h], confidence: clamp01(c[h].confidence) }])),
      critical_incident_risk: isNum(c.critical_incident_risk) ? clamp01(c.critical_incident_risk) : null,
      disagreements: strs(c.disagreements),
    } as TriageResponse["classification"],
    escalation: {
      status: known ? e.status : "escalate",
      reasons,
      thresholds: {
        confidence: isNum(t.confidence) ? t.confidence : 0.55,
        similarity: isNum(t.similarity) ? t.similarity : 0.45,
        critical_incident_risk: isNum(t.critical_incident_risk) ? t.critical_incident_risk : null,
      },
    },
    route: isObj(raw.route) && isStr(raw.route.path) ? { path: raw.route.path, reasons: strs(raw.route.reasons) } : { path: "none", reasons: [] },
    guardrails: {
      prompt_injection: flag(g.prompt_injection),
      unsupported_request: flag(g.unsupported_request),
      injection_signals: strs(g.injection_signals),
      removed_claims: strs(g.removed_claims),
      verification_issues: strs(g.verification_issues),
      citations_valid: g.citations_valid !== false,
    },
    draft: isObj(d) && isStr(d.text) ? { language: isStr(d.language) ? d.language : "en", text: d.text, citations: strs(d.citations) } : null,
    usage: isObj(raw.usage) && isNum(raw.usage.estimated_cost_usd) ? raw.usage : undefined,
  } as TriageResponse;
}

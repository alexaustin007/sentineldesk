// Tiny check for parseTriageResponse, no test framework.
// Run: node ui/src/lib/validate.test.ts   (Node ≥ 22.18 strips types natively)
// Excluded from tsc (see ui/tsconfig.json) because it uses node:assert.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseTriageResponse, TriageError } from "./validate.ts";

const contract = JSON.parse(readFileSync(new URL("../../../contracts/triage_response.example.json", import.meta.url), "utf8"));
let n = 0;
const ok = (name: string, fn: () => void) => {
  fn();
  n++;
  console.log(`ok  ${name}`);
};
const throwsBad = (raw: unknown, re: RegExp) =>
  assert.throws(
    () => parseTriageResponse(raw),
    (e: unknown) => e instanceof TriageError && e.code === "BAD_RESPONSE" && re.test(e.message),
  );

ok("contract example passes unchanged", () => {
  const r = parseTriageResponse(contract);
  assert.equal(r.escalation.status, "escalate");
  assert.equal(r.escalation.reasons.length, 1);
  assert.equal(r.precedents.length, 2);
});

ok("PR #5 raw shape gets the specific message", () => throwsBad({ status: "ESCALATE_IMMEDIATELY", final_labels: {} }, /PR #5's raw TriageResult/));

ok("every bad required path is listed", () =>
  throwsBad(
    { ...contract, classification: { type: { label: 3 } }, precedents: [{ ticket_id: "TKT-1" }], latency_ms: {} },
    /classification\.type\.label, classification\.type\.confidence, classification\.queue\.label.*precedents\[0\]\.similarity, latency_ms\.total/,
  ));

ok("non-object body is rejected", () => throwsBad("nope", /not a JSON object/));

ok("missing escalation → escalate + OTHER reason; defaults filled; confidences clamped", () => {
  const r = parseTriageResponse({
    classification: {
      type: { label: "Incident", confidence: 1.4 },
      queue: { label: "Technical Support", confidence: 0.7 },
      priority: { label: "high", confidence: -1 },
    },
    precedents: [],
    latency_ms: { total: 10 },
  });
  assert.equal(r.escalation.status, "escalate");
  assert.equal(r.escalation.reasons[0].code, "OTHER");
  assert.deepEqual(r.escalation.thresholds, { confidence: 0.55, similarity: 0.45, critical_incident_risk: null });
  assert.equal(r.classification.type.confidence, 1);
  assert.equal(r.classification.priority.confidence, 0);
  assert.deepEqual(r.classification.disagreements, []);
  assert.deepEqual(r.guardrails.removed_claims, []);
  assert.equal(r.draft, null);
  assert.equal(r.input.language_detected, "en");
  assert.equal(r.input.language_missing, true);
  assert.equal(r.route.path, "none");
  assert.equal(r.usage, undefined);
});

ok("unknown status → escalate, backend reasons kept after the OTHER note", () => {
  const r = parseTriageResponse({ ...contract, escalation: { status: "maybe", reasons: [{ message: "x" }] } });
  assert.equal(r.escalation.status, "escalate");
  assert.deepEqual(
    r.escalation.reasons.map((x) => x.message),
    ["Backend sent no escalation decision; treated as escalate", "x"],
  );
});

for (const name of ["vpnOutage", "deBilling", "knowledgeGap", "injection", "humanReviewDeep", "lowConfidence"]) {
  const mod = await import(`../mocks/${name}.ts`);
  ok(`mock ${name} passes`, () => {
    const r = parseTriageResponse(mod[name]);
    assert.equal(r.precedents.length, mod[name].precedents.length);
  });
}

console.log(`\n${n} checks passed`);

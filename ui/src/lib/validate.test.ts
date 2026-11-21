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

const { injection } = await import("../mocks/injection.ts");
ok("injection mock matches PR #5's early return (screening before routing, drafting and LLM calls)", () => {
  const r = parseTriageResponse(injection);
  assert.equal(r.escalation.status, "human_review");
  assert.deepEqual(r.escalation.reasons.map((x) => x.code), ["PROMPT_INJECTION"]);
  assert.equal(r.route.path, "none");
  assert.equal(r.draft, null);
  assert.equal(r.usage?.estimated_cost_usd ?? 0, 0);
  assert.deepEqual(Object.keys(r.latency_ms).filter((k) => k !== "total").sort(), ["classifier", "guardrails", "retrieval"]);
  assert.ok(r.latency_ms.total < 500);
});

const { findCitations } = await import("./citations.ts");
ok("citations: plain and prefixed IDs are extracted; malformed ones are not", () => {
  const text = "See [TKT-01842], also [TKT-V5-00042] and [TKT-A1-B2-12345]; not [TKT-1], [TKT-V5-1], TKT-01842 or [tkt-01842].";
  assert.deepEqual(
    findCitations(text).map((c) => c.id),
    ["TKT-01842", "TKT-V5-00042", "TKT-A1-B2-12345"],
  );
  const c = findCitations(text)[1];
  assert.equal(text.slice(c.index, c.index + c.length), "[TKT-V5-00042]");
});

ok("every citation in every mock draft resolves to a precedent (except the deliberate bad one) and a TKT-V5 ID is covered", async () => {
  const { deBilling } = await import("../mocks/deBilling.ts");
  const ids = new Set(deBilling.precedents.map((p) => p.ticket_id));
  const cited = findCitations(deBilling.draft!.text).map((c) => c.id);
  assert.deepEqual(cited, deBilling.draft!.citations);
  assert.ok(cited.every((id) => ids.has(id)));
  assert.ok(cited.some((id) => id.startsWith("TKT-V5-")), "deBilling cites a TKT-V5 precedent");
});

// --- metrics.json ---
const { parseMetrics, MetricsError } = await import("./validateMetrics.ts");
const metrics = JSON.parse(readFileSync(new URL("../../../contracts/metrics.example.json", import.meta.url), "utf8"));
const throwsMetrics = (raw: unknown, re: RegExp) =>
  assert.throws(
    () => parseMetrics(raw),
    (e: unknown) => e instanceof MetricsError && re.test(e.message),
  );

ok("metrics example passes, sample flag kept", () => {
  const m = parseMetrics(metrics);
  assert.equal(m.sample, true);
  assert.equal(m.heads.queue.confusion.length, m.heads.queue.labels.length);
});

ok("metrics example is self-consistent (support = confusion row sums)", () => {
  for (const h of ["type", "queue", "priority"] as const) {
    const head = metrics.heads[h];
    head.labels.forEach((l: string, i: number) => {
      const row = head.confusion[i].reduce((a: number, b: number) => a + b, 0);
      assert.equal(head.per_class.find((c: { label: string }) => c.label === l).support, row, `${h}/${l}`);
    });
  }
});

ok("non-square confusion and missing recall are both listed", () =>
  throwsMetrics(
    { ...metrics, heads: { ...metrics.heads, queue: { ...metrics.heads.queue, confusion: [[1, 2]] } }, high_priority_incident_recall: "x" },
    /heads\.queue\.confusion \(must be 10×10.*high_priority_incident_recall/,
  ));

ok("hover fields: HPI counts match the recall, trade-off rows carry precision + tickets", () => {
  const m = parseMetrics(metrics);
  const c = m.high_priority_incident!;
  assert.equal(Math.round((c.caught / c.total) * 1000) / 1000, m.high_priority_incident_recall);
  for (const r of m.escalation_tradeoff!) {
    assert.equal(typeof r.precision, "number");
    assert.equal(r.tickets_escalated, Math.round(r.escalation_rate * metrics.split.holdout));
  }
  assert.equal(typeof m.pipeline?.cost_basis, "string");
  assert.equal(typeof m.split?.leakage_detail, "string");
});

ok("panel fields agree: urgent caught = recall × total = precision × escalated; cost breakdown sums", () => {
  const m = parseMetrics(metrics);
  const total = m.high_priority_incident!.total;
  for (const r of m.escalation_tradeoff!) {
    assert.ok(Math.abs(r.precision! * r.tickets_escalated! - r.target_recall * total) <= 1, `row ${r.target_recall}`);
  }
  const costs = Object.values(m.pipeline!.cost_breakdown_usd!);
  assert.ok(Math.abs(costs.reduce((a, b) => a + b, 0) - m.pipeline!.avg_cost_usd!) < 1e-9);
  assert.ok(Object.keys(m.pipeline!.stage_latency_ms!).includes("draft_reply"));
  const bad = parseMetrics({ ...metrics, pipeline: { ...metrics.pipeline, stage_latency_ms: { x: "slow" }, cost_breakdown_usd: 3 } });
  assert.equal(bad.pipeline?.stage_latency_ms, null);
  assert.equal(bad.pipeline?.cost_breakdown_usd, null);
});

ok("malformed hover fields are dropped, not fatal", () => {
  const m = parseMetrics({ ...metrics, high_priority_incident: { caught: "x", total: 0 }, escalation_tradeoff: [{ target_recall: 0.9, escalation_rate: 0.2, precision: "?" }] });
  assert.equal(m.high_priority_incident, null);
  assert.equal(m.escalation_tradeoff![0].precision, undefined);
});

const { mostConfused } = await import("./metricsText.ts");
ok("most often confused comes from the largest off-diagonal cell", () => {
  const m = parseMetrics(metrics);
  const t = mostConfused(m.heads.type);
  assert.deepEqual(t, { from: "Problem", to: "Incident", count: 138 });
  assert.equal(mostConfused({ labels: ["a", "b"], per_class: [], macro_f1: 1, confusion: [[5, 0], [0, 7]] }), null);
});

ok("calibration, language split and draft quality: kept when valid, dropped when not", () => {
  const m = parseMetrics(metrics);
  for (const h of ["type", "queue", "priority"] as const) {
    const head = m.heads[h];
    assert.equal(typeof head.calibration_error, "number");
    const l = head.macro_f1_by_language!;
    // English and German scores bracket the overall macro-F1.
    assert.ok(Math.min(l.en, l.de) <= head.macro_f1 && head.macro_f1 <= Math.max(l.en, l.de), `${h} language split brackets macro-F1`);
  }
  assert.equal(typeof m.calibration_error, "number");
  assert.equal(m.drafts, null); // null in the example
  const withDrafts = parseMetrics({ ...metrics, drafts: { citations_valid_rate: 0.97, language_match_rate: null, removed_claims_rate: 0.04 } });
  assert.deepEqual(withDrafts.drafts, { citations_valid_rate: 0.97, language_match_rate: null, removed_claims_rate: 0.04 });
  assert.equal(parseMetrics({ ...metrics, drafts: { citations_valid_rate: null, language_match_rate: null, removed_claims_rate: null } }).drafts, null);
  const bad = parseMetrics({ ...metrics, heads: { ...metrics.heads, type: { ...metrics.heads.type, calibration_error: "low", macro_f1_by_language: { en: 0.8 } } } });
  assert.equal(bad.heads.type.calibration_error, undefined);
  assert.equal(bad.heads.type.macro_f1_by_language, undefined);
});

ok("missing optional parts are dropped, not fatal", () => {
  const m = parseMetrics({ heads: metrics.heads, high_priority_incident_recall: 0.9, pipeline: { status_mix: { auto_draft: 1 } } });
  assert.deepEqual(m.escalation_tradeoff, []);
  assert.equal(m.pipeline?.status_mix, null);
  assert.equal(m.split, undefined);
});

console.log(`\n${n} checks passed`);

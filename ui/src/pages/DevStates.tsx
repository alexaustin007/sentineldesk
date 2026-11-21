import { useEffect, type ReactNode } from "react";
import contractExample from "../../../contracts/triage_response.example.json";
import metricsExample from "../../../contracts/metrics.example.json";
import { ConsoleView } from "../components/ConsoleView";
import { EntryView } from "../components/EntryView";
import { deBilling, humanReviewDeep, injection, knowledgeGap, lowConfidence, vpnOutage } from "../mocks";
import type { RunState } from "../lib/run";
import { parseTriageResponse, type TriageError } from "../lib/validate";
import { parseMetrics } from "../lib/validateMetrics";
import { MetricsInvalid, MetricsLoading, MetricsView } from "./MetricsPage";
import type { TriageResponse } from "../types/triage";

// Type-checks the frozen contract example against ui/src/types/triage.ts at build time.
const contract: TriageResponse = contractExample;

const noop = () => {};

function success(res: TriageResponse): RunState {
  return { kind: "success", res, runId: 1 };
}

interface Case {
  id: string;
  title: string;
  run: RunState;
  input?: { subject: string | null; body: string };
  bodyError?: boolean;
}

const edge = (patch: Partial<TriageResponse>, base = vpnOutage): TriageResponse => ({ ...base, ...patch });

/** Runs raw JSON through the real runtime check, exactly as liveTriage does. */
function parsed(raw: unknown): RunState {
  try {
    return success(parseTriageResponse(raw));
  } catch (e) {
    const err = e as TriageError;
    return { kind: "error", code: err.code ?? "CLIENT", message: err.message, elapsedMs: 240 };
  }
}

const CASES: Case[] = [
  { id: "entry", title: "Entry only (before first submit)", run: { kind: "idle" }, input: { subject: "", body: "" } },
  { id: "validation", title: "Entry · empty body validation", run: { kind: "idle" }, input: { subject: "Login issue", body: "" }, bodyError: true },
  { id: "loading", title: "Loading · pipeline steps (live)", run: { kind: "loading", startedAt: Date.now() }, input: vpnOutage.input },
  {
    id: "error",
    title: "Backend error · retry",
    run: { kind: "error", code: "UPSTREAM_UNAVAILABLE", message: "The generator service did not respond.", elapsedMs: 820 },
    input: vpnOutage.input,
  },
  { id: "timeout", title: "Timeout > 30 s · retry", run: { kind: "timeout", elapsedMs: 30000 }, input: vpnOutage.input },
  {
    id: "bad-response",
    title: "BAD_RESPONSE · wrong-shaped JSON (parseTriageResponse)",
    run: parsed({
      ...vpnOutage,
      classification: { type: { label: 3, confidence: 0.9 }, queue: { label: "Technical Support" } },
      precedents: [{ ticket_id: "TKT-01842" }],
      latency_ms: {},
    }),
    input: vpnOutage.input,
  },
  {
    id: "raw-pr5-shape",
    title: "BAD_RESPONSE · PR #5 raw TriageResult (final_labels, no classification)",
    run: parsed({
      status: "ESCALATE_IMMEDIATELY",
      reasons: ["High-priority Incident"],
      final_labels: { type: { label: "Incident", confidence: 0.91 } },
      route: "none",
      latency_ms: 182,
    }),
    input: vpnOutage.input,
  },
  {
    id: "normalized",
    title: "Minimal valid response · normalized (no escalation/guardrails/draft/route/usage/language)",
    run: parsed({
      classification: {
        type: { label: "Incident", confidence: 1.4 },
        queue: { label: "Technical Support", confidence: 0.78 },
        priority: { label: "high", confidence: -0.2 },
      },
      precedents: [{ ticket_id: "TKT-01842", similarity: 0.83, type: "Incident", queue: "Technical Support", priority: "high", answer_snippet: "Rolled back the gateway firmware." }],
      latency_ms: { total: 210 },
    }),
    input: vpnOutage.input,
  },
  { id: "a", title: "A · Escalate (red) · VPN outage, draft: null", run: success(vpnOutage) },
  { id: "b", title: "B · Auto-draft (green) · German billing", run: success(deBilling) },
  { id: "c", title: "C · Human review (amber) · knowledge gap · no subject", run: success(knowledgeGap) },
  { id: "d", title: "D · Human review (amber) · injection attempt, blocked before drafting", run: success(injection) },
  {
    id: "e",
    title: "E · Human review (amber) · deep route · queue disagreement · removed claim · reason without code · precedent without lang/subject",
    run: success(humanReviewDeep),
  },
  {
    id: "unknown-code",
    title: "Unknown reason code + OTHER render verbatim",
    run: success(
      edge(
        {
          escalation: {
            status: "human_review",
            reasons: [
              { code: "SOMETHING_NEW", message: "A rule the UI has never heard of fired" },
              { code: "OTHER", message: "Free-text reason from the gate" },
            ],
            thresholds: deBilling.escalation.thresholds,
          },
        },
        deBilling,
      ),
    ),
  },
  {
    id: "low",
    title: "Low confidence · unknown priority “critical” · missing status → escalate · invalid citation",
    run: success(lowConfidence),
  },
  { id: "contract", title: "Contract example (contracts/triage_response.example.json)", run: success(contract) },
  {
    id: "unknown-status",
    title: "Unknown status “maybe” → escalate · auto-draft null draft",
    run: success(edge({ escalation: { ...deBilling.escalation, status: "maybe" }, draft: null }, deBilling)),
  },
  {
    id: "auto-null",
    title: "Auto-draft with draft: null",
    run: success(edge({ draft: null }, deBilling)),
  },
  {
    id: "no-thresholds",
    title: "Missing thresholds + no precedents",
    run: success(
      edge({
        escalation: { status: "escalate", reasons: [{ code: "LOW_SIMILARITY", message: "no precedents" }] },
        precedents: [],
        draft: null,
      }),
    ),
  },
];

// ---- Metrics tab states (spec: docs/ui-specs/metrics.md) ----
// eslint-disable-next-line @typescript-eslint/no-explicit-any -- building deliberately broken/partial files
type Obj = Record<string, any>;
const sample = () => structuredClone(metricsExample) as unknown as Obj;

function minimalMetrics(): Obj {
  // Only the required fields: every optional column, row and fact must disappear without empty cells.
  const m = sample();
  delete m.sample;
  for (const h of Object.values(m.heads) as Obj[]) {
    delete h.accuracy;
    delete h.calibration_error;
    delete h.macro_f1_by_language;
  }
  for (const k of ["calibration_error", "drafts", "high_priority_incident", "escalation_tradeoff", "pipeline", "split", "model", "dataset", "generated_at"]) delete m[k];
  return m;
}

function invalidMessage(): string {
  const m = sample();
  m.high_priority_incident_recall = "n/a";
  m.heads.queue.confusion = [[1, 2]];
  try {
    parseMetrics(m);
  } catch (e) {
    return (e as Error).message;
  }
  return "";
}

const METRICS_CASES: { id: string; title: string; node: ReactNode }[] = [
  { id: "metrics-sample", title: "Metrics · sample data (the bundled example)", node: <MetricsView metrics={parseMetrics(sample())} source="sample" /> },
  {
    id: "metrics-real",
    title: "Metrics · real data (no sample notice)",
    node: <MetricsView metrics={parseMetrics({ ...sample(), sample: false })} source="live" />,
  },
  {
    id: "metrics-drafts",
    title: "Metrics · drafts present (extra Draft quality fact)",
    node: (
      <MetricsView
        metrics={parseMetrics({ ...sample(), sample: false, drafts: { citations_valid_rate: 0.974, language_match_rate: 0.991, removed_claims_rate: 0.042 } })}
        source="live"
      />
    ),
  },
  { id: "metrics-minimal", title: "Metrics · optional fields missing (columns, rows and facts hidden)", node: <MetricsView metrics={parseMetrics(minimalMetrics())} source="live" /> },
  { id: "metrics-invalid", title: "Metrics · invalid file (inline message + Retry)", node: <MetricsInvalid message={invalidMessage()} onRetry={noop} /> },
  { id: "metrics-loading", title: "Metrics · loading (section titles with placeholders)", node: <MetricsLoading /> },
];

export function DevStates() {
  useEffect(() => {
    if (window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
  }, []);
  return (
    <div className="flex flex-col gap-10">
      <nav className="flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
        {[...CASES, ...METRICS_CASES].map((c) => (
          <a key={c.id} href={`#${c.id}`} className="text-accent hover:underline">
            {c.id.startsWith("metrics-") ? c.id.replace("metrics-", "Metrics ") : c.title.split(" · ")[0]}
          </a>
        ))}
      </nav>
      {CASES.map((c) => (
        <Frame key={c.id} id={c.id} title={c.title}>
          {c.run.kind === "idle" ? (
            <div className="rounded-lg border border-line bg-bg">
              <EntryView
                subject={c.input?.subject ?? ""}
                body={c.input?.body ?? ""}
                onSubject={noop}
                onBody={noop}
                onSample={noop}
                onSubmit={noop}
                bodyError={!!c.bodyError}
                readOnly
              />
            </div>
          ) : (
          <ConsoleView
            subject={(c.input ?? (c.run.kind === "success" ? c.run.res.input : null))?.subject ?? ""}
            body={(c.input ?? (c.run.kind === "success" ? c.run.res.input : null))?.body ?? ""}
            resultBody={c.run.kind === "success" ? c.run.res.input.body : null}
            onSubject={noop}
            onBody={noop}
            onSample={noop}
            onSubmit={noop}
            onRetry={noop}
            run={c.run}
            bodyError={!!c.bodyError}
            readOnly
            framed
            onNew={noop}
          />
          )}
        </Frame>
      ))}
      {METRICS_CASES.map((c) => (
        <Frame key={c.id} id={c.id} title={c.title}>
          <div className="rounded-lg border border-line bg-bg px-6 pt-6">{c.node}</div>
        </Frame>
      ))}
    </div>
  );
}

function Frame({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-16">
      <h2 className="num mb-3 border-b border-line pb-1 text-[12px] text-ink-3">
        /dev/states#{id} · {title}
      </h2>
      {children}
    </section>
  );
}

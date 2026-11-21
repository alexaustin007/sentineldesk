import { useEffect, type ReactNode } from "react";
import contractExample from "../../../contracts/triage_response.example.json";
import { ConsoleView } from "../components/ConsoleView";
import { EntryView } from "../components/EntryView";
import { deBilling, injection, knowledgeGap, lowConfidence, vpnOutage } from "../mocks";
import type { RunState } from "../lib/run";
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
  { id: "a", title: "A · Escalated · VPN outage (chip 1)", run: success(vpnOutage) },
  { id: "b", title: "B · Auto-draft · DE billing (chip 2)", run: success(deBilling) },
  { id: "c", title: "C · Knowledge gap · no subject (chip 4)", run: success(knowledgeGap) },
  { id: "d", title: "D · Guardrail hit · injection (chip 3)", run: success(injection) },
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

export function DevStates() {
  useEffect(() => {
    if (window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
  }, []);
  return (
    <div className="flex flex-col gap-10">
      <nav className="flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
        {CASES.map((c) => (
          <a key={c.id} href={`#${c.id}`} className="text-accent hover:underline">
            {c.title.split(" · ")[0]}
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

import { useRef, useState, type ReactNode } from "react";
import { TIMEOUT_MS } from "../lib/api";
import type { RunState } from "../lib/run";
import { Classification } from "./Classification";
import { DraftReply } from "./DraftReply";
import { EscalationBanner } from "./EscalationBanner";
import { Precedents, type PrecedentsHandle } from "./Precedents";

/** Results read top to bottom: decision → classification → draft → evidence (B2). ≤5 sections (C1). */
export function ResultsPane({ run, onRetry }: { run: RunState; onRetry: () => void }) {
  if (run.kind === "idle") return null; // the console shows EntryView instead
  if (run.kind === "loading") return <Loading />;
  if (run.kind === "error")
    return (
      <Failure
        title={run.code === "BAD_RESPONSE" ? "Unexpected backend response" : "Triage failed"}
        detail={run.message}
        code={run.code}
        onRetry={onRetry}
      />
    );
  if (run.kind === "timeout")
    return (
      <Failure
        title={`No response after ${TIMEOUT_MS / 1000} s`}
        detail="The pipeline took too long. Your ticket is unchanged on the left."
        code="TIMEOUT"
        onRetry={onRetry}
      />
    );
  return <Success key={run.runId} run={run} />;
}

function Success({ run }: { run: Extract<RunState, { kind: "success" }> }) {
  const precedents = useRef<PrecedentsHandle>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const { res } = run;
  return (
    <div className="flex flex-col gap-6">
      {/* Sections arrive in reading order (B2): decision, classification, draft, evidence. */}
      <Reveal i={0}>
        <EscalationBanner res={res} />
      </Reveal>
      <Reveal i={1}>
        <Classification res={res} />
      </Reveal>
      <Reveal i={2}>
        <DraftReply res={res} onCite={(id) => precedents.current?.focus(id)} onHover={setHoverId} />
      </Reveal>
      <Reveal i={3}>
        <Precedents ref={precedents} res={res} hoverId={hoverId} />
      </Reveal>
    </div>
  );
}

const GHOSTS = [
  ["Decision", "h-32"],
  ["Classification", "h-40"],
  ["Draft reply", "h-48"],
  ["Precedents", "h-36"],
] as const;

function Reveal({ i, children }: { i: number; children: ReactNode }) {
  return (
    <div className="rise" style={{ animationDelay: `${i * 90}ms` }}>
      {children}
    </div>
  );
}

function Loading() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Triaging ticket">
      {GHOSTS.map(([g, h], i) => (
        <div key={g} className={`rise rounded-xl border border-line bg-surface ${h} px-6 py-5`} style={{ animationDelay: `${i * 120}ms` }}>
          <span className="heading !text-ink-3">{g}</span>
          <div className="mt-4 space-y-3">
            <div className="h-2.5 w-2/3 animate-pulse rounded-full bg-surface-2" />
            <div className="h-2.5 w-1/2 animate-pulse rounded-full bg-surface-2" />
            {i > 0 && <div className="h-2.5 w-1/3 animate-pulse rounded-full bg-surface-2" />}
          </div>
        </div>
      ))}
    </div>
  );
}

function Failure({ title, detail, code, onRetry }: { title: string; detail: string; code: string; onRetry: () => void }) {
  return (
    <section role="alert" className="relative overflow-hidden rounded-xl border border-line bg-surface py-6 pr-6 pl-8">
      <span aria-hidden className="absolute inset-y-0 left-0 w-1.5 bg-ink-3" />
      <p className="label">Triage did not complete</p>
      <p className="mt-1 text-[20px] font-semibold text-ink">{title}</p>
      <p className="mt-1.5 text-[15px] text-ink-2">{detail}</p>
      <div className="mt-5 flex items-center gap-4">
        <button
          type="button"
          onClick={onRetry}
          className="h-10 rounded-lg border border-field bg-surface px-4 text-[14.5px] font-semibold text-ink hover:border-ink-2"
        >
          Retry
        </button>
        <span className="mono text-[13px] text-ink-3">{code}</span>
      </div>
    </section>
  );
}

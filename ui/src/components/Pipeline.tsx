import { useEffect, useState } from "react";
import { fmtMs, fmtSeconds, stageName } from "../lib/labels";
import type { RunState } from "../lib/run";
import { PIPELINE_STAGES, type PipelineStage } from "../types/triage";
import { IconCheck, IconChevron, IconSpinner } from "./Icons";

type StepStatus = "pending" | "active" | "done" | "stopped";
interface Step {
  key: string;
  st: StepStatus;
}

// While waiting we don't know the route yet, so show the stages every routed ticket runs
// (adversarial review only appears in the result when the deep route ran).
const LOADING_STAGES: PipelineStage[] = ["guardrails", "classifier", "retrieval", "draft_reply", "verification"];
// The API returns timings only at the end, so the list advances on a plausible schedule
// (guardrails/classifier/retrieval are fast) and sits on "draft reply" until the response lands.
const ESTIMATE_DONE_AT: Partial<Record<PipelineStage, number>> = { guardrails: 80, classifier: 200, retrieval: 600 };

function stepsFor(run: RunState, elapsed: number): Step[] {
  if (run.kind === "success") {
    // Only stages present in latency_ms, canonical order first, then any unknown keys.
    const keys = Object.keys(run.res.latency_ms).filter((k) => k !== "total" && run.res.latency_ms[k] != null);
    const known = PIPELINE_STAGES.filter((s) => keys.includes(s));
    const extra = keys.filter((k) => !(PIPELINE_STAGES as readonly string[]).includes(k));
    return [...known, ...extra].map((key) => ({ key, st: "done" }));
  }
  if (run.kind === "idle") return LOADING_STAGES.map((key) => ({ key, st: "pending" }));
  const at = run.kind === "loading" ? elapsed : run.elapsedMs;
  let activeSet = false;
  return LOADING_STAGES.map((key) => {
    const doneAt = ESTIMATE_DONE_AT[key];
    if (doneAt != null && at >= doneAt) return { key, st: "done" };
    if (!activeSet) {
      activeSet = true;
      // On failure we don't know which stage broke (the backend doesn't say), so the
      // step that was in progress is marked "stopped", not "failed" (review #8).
      return { key, st: run.kind === "loading" ? "active" : "stopped" };
    }
    return { key, st: "pending" };
  });
}

function Marker({ st }: { st: StepStatus }) {
  const ring = "relative z-10 grid h-5 w-5 place-items-center rounded-full border";
  if (st === "done")
    return (
      <span className={`${ring} border-ink-2 bg-ink-2 text-surface`}>
        <IconCheck className="!h-3 !w-3" />
      </span>
    );
  if (st === "active")
    return (
      <span className={`${ring} border-accent bg-surface text-accent`}>
        <IconSpinner className="!h-3 !w-3" />
      </span>
    );
  if (st === "stopped")
    return (
      <span className={`${ring} border-tone-high bg-surface`}>
        <span className="h-2 w-2 rounded-[1px] bg-tone-high" />
      </span>
    );
  return <span className={`${ring} border-ink-4 bg-surface`} />;
}

export function Pipeline({ run }: { run: RunState }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (run.kind !== "loading") return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [run.kind]);

  const elapsed = run.kind === "loading" ? Math.max(0, now - run.startedAt) : 0;
  const steps = stepsFor(run, elapsed);
  const total = run.kind === "success" ? run.res.latency_ms.total : null;
  const path = run.kind === "success" ? run.res.route?.path : undefined;
  const route = path === "fast" || path === "deep" ? path : null;
  const routeReasons = run.kind === "success" ? run.res.route?.reasons?.join(" · ") : undefined;

  const [totalNote, totalText] =
    run.kind === "success"
      ? ["", fmtSeconds(run.res.latency_ms.total)]
      : run.kind === "loading"
        ? ["running", fmtSeconds(elapsed)]
        : run.kind === "error"
          ? ["failed after", fmtSeconds(run.elapsedMs)]
          : run.kind === "timeout"
            ? ["timed out after", fmtSeconds(run.elapsedMs)]
            : ["", "—"];

  // Calm on first open: once a result is in, the step list collapses to one summary line.
  const done = run.kind === "success";
  const [expanded, setExpanded] = useState(false);
  const runKey = run.kind === "success" ? run.runId : run.kind;
  useEffect(() => setExpanded(false), [runKey]);

  if (done && !expanded) {
    return (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        aria-expanded={false}
        className="-mx-2 flex h-10 items-center gap-2 rounded-lg px-2 text-left text-[14.5px] text-ink-2 hover:bg-surface-2 hover:text-ink"
      >
        <IconCheck className="text-ink-3" />
        <span>
          Completed in <span className="num font-medium text-ink">{totalText}</span> · {steps.length} step{steps.length === 1 ? "" : "s"}
          {route && <span className="text-ink-3"> · {route} route</span>}
        </span>
        <IconChevron className="text-ink-3" />
      </button>
    );
  }

  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <span className="flex items-baseline gap-2">
          {done ? (
            <button
              type="button"
              onClick={() => setExpanded(false)}
              aria-expanded
              className="flex items-center gap-1.5 text-[15px] font-semibold text-ink hover:text-ink-2"
            >
              Pipeline <IconChevron open />
            </button>
          ) : (
            <h2 className="text-[15px] font-semibold text-ink">Pipeline</h2>
          )}
          {route && (
            <span className="rounded-md bg-surface-2 px-2 py-0.5 text-[12.5px] text-ink-2" title={routeReasons}>
              {route} route
            </span>
          )}
        </span>
        <span className="flex items-baseline gap-2">
          {totalNote && <span className={`text-[13px] ${run.kind === "loading" ? "text-ink-3" : "text-tone-high"}`}>{totalNote}</span>}
          <span className="num text-[18px] font-medium text-ink">{totalText}</span>
        </span>
      </div>
      <ol className="relative">
        {steps.map(({ key: s, st }, i) => {
          const ms = run.kind === "success" ? run.res.latency_ms[s] : undefined;
          const share = total && ms != null ? Math.max(2, (ms / total) * 100) : 0;
          const last = i === steps.length - 1;
          return (
            <li key={s} className="relative grid grid-cols-[20px_minmax(0,1fr)] gap-x-3 pb-3.5 last:pb-0">
              {!last && (
                <span
                  aria-hidden
                  className={`absolute top-5 bottom-0 left-[9.5px] w-px ${st === "done" ? "bg-ink-3" : "bg-line-strong"}`}
                />
              )}
              <Marker st={st} />
              <div className="min-w-0">
                <div className="flex h-5 items-center justify-between gap-2 text-[14.5px]">
                  <span className={st === "pending" ? "text-ink-3" : "font-medium text-ink"}>{stageName(s)}</span>
                  <span className={`num text-[14px] ${st === "stopped" ? "text-tone-high" : "text-ink-2"}`}>
                    {ms != null ? fmtMs(ms) : st === "stopped" ? "stopped" : st === "active" ? "…" : ""}
                  </span>
                </div>
                <div className="mt-1.5 h-1 rounded-full bg-bar-track">
                  {share > 0 && <div className="h-full rounded-full bg-bar" style={{ width: `${share}%` }} />}
                  {st === "active" && <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

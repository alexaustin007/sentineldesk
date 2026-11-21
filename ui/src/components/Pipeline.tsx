import { useEffect, useState } from "react";
import { fmtMs, fmtSeconds } from "../lib/labels";
import type { RunState } from "../lib/run";
import { PIPELINE_STAGES, type PipelineStage } from "../types/triage";
import { IconCheck, IconSpinner } from "./Icons";

type StepStatus = "pending" | "active" | "done" | "stopped" | "skipped";

// The API returns timings only at the end, so while waiting the list advances on a
// plausible schedule (classify/retrieve are fast) and sits on "generate" until the response lands.
const ESTIMATE_DONE_AT: Partial<Record<PipelineStage, number>> = { classify: 250, retrieve: 700 };

function stepsFor(run: RunState, elapsed: number): Record<PipelineStage, StepStatus> {
  const out = {} as Record<PipelineStage, StepStatus>;
  if (run.kind === "idle") {
    PIPELINE_STAGES.forEach((s) => (out[s] = "pending"));
    return out;
  }
  if (run.kind === "success") {
    PIPELINE_STAGES.forEach((s) => (out[s] = run.res.latency_ms[s] == null ? "skipped" : "done"));
    return out;
  }
  const at = run.kind === "loading" ? elapsed : run.elapsedMs;
  let activeSet = false;
  for (const s of PIPELINE_STAGES) {
    const doneAt = ESTIMATE_DONE_AT[s];
    if (doneAt != null && at >= doneAt) out[s] = "done";
    else if (!activeSet) {
      // On failure we don't know which stage broke (the backend doesn't say), so the
      // step that was in progress is marked "stopped", not "failed" (review #8).
      out[s] = run.kind === "loading" ? "active" : "stopped";
      activeSet = true;
    } else out[s] = "pending";
  }
  return out;
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
  if (st === "skipped") return <span className={`${ring} border-dashed border-ink-4 bg-surface`} />;
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

  return (
    <div>
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="label">Pipeline</h2>
        <span className="flex items-baseline gap-2">
          {totalNote && <span className={`text-[12px] ${run.kind === "loading" ? "text-ink-3" : "text-tone-high"}`}>{totalNote}</span>}
          <span className="num text-[18px] font-medium text-ink">{totalText}</span>
        </span>
      </div>
      <ol className="relative">
        {PIPELINE_STAGES.map((s, i) => {
          const st = steps[s];
          const ms = run.kind === "success" ? run.res.latency_ms[s] : undefined;
          const share = total && ms != null ? Math.max(2, (ms / total) * 100) : 0;
          const last = i === PIPELINE_STAGES.length - 1;
          return (
            <li key={s} className="relative grid grid-cols-[20px_minmax(0,1fr)] gap-x-3 pb-3 last:pb-0">
              {!last && (
                <span
                  aria-hidden
                  className={`absolute top-5 bottom-0 left-[9.5px] w-px ${st === "done" ? "bg-ink-3" : "bg-line-strong"}`}
                />
              )}
              <Marker st={st} />
              <div className="min-w-0">
                <div className="flex h-5 items-center justify-between gap-2 text-[13px]">
                  <span className={st === "pending" || st === "skipped" ? "text-ink-3" : "font-medium text-ink"}>{s}</span>
                  <span className={`num text-[12.5px] ${st === "stopped" ? "text-tone-high" : "text-ink-2"}`}>
                    {ms != null ? fmtMs(ms) : st === "skipped" ? "skipped" : st === "stopped" ? "stopped" : st === "active" ? "…" : ""}
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

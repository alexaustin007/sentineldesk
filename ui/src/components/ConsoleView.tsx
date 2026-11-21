import type { Sample } from "../mocks";
import type { RunState } from "../lib/run";
import { Pipeline } from "./Pipeline";
import { ResultsPane } from "./ResultsPane";
import { TicketInput } from "./TicketInput";

export interface ConsoleViewProps {
  subject: string;
  body: string;
  onSubject: (v: string) => void;
  onBody: (v: string) => void;
  onSample: (s: Sample) => void;
  onSubmit: () => void;
  onRetry: () => void;
  run: RunState;
  bodyError: boolean;
  /** Body text the current result was computed for; evidence is highlighted only while it matches. */
  resultBody: string | null;
  readOnly?: boolean;
  /** Full-viewport sidebar (console) vs. framed (dev states). */
  framed?: boolean;
  /** Back to the entry-only view. */
  onNew?: () => void;
}

/** Two panes at ≥1024 px (C6): ticket stays visible in a sidebar next to results. Stacks below. */
export function ConsoleView(p: ConsoleViewProps) {
  const evidence =
    p.run.kind === "success" && p.resultBody === p.body
      ? [p.run.res.guardrails?.prompt_injection?.evidence, p.run.res.guardrails?.unsupported_request?.evidence].filter(
          (e): e is string => !!e,
        )
      : [];
  const sticky = p.framed ? "" : "lg:sticky lg:top-12 lg:h-[calc(100vh-48px)] lg:overflow-y-auto";
  return (
    <div
      className={`grid lg:grid-cols-[420px_minmax(0,1fr)] ${
        p.framed ? "overflow-hidden rounded-lg border border-line" : "min-h-[calc(100vh-48px)]"
      }`}
    >
      <aside className={`flex flex-col gap-8 border-b border-line bg-surface px-7 py-6 lg:border-r lg:border-b-0 ${sticky}`}>
        <TicketInput
          subject={p.subject}
          body={p.body}
          onSubject={p.onSubject}
          onBody={p.onBody}
          onSample={p.onSample}
          onSubmit={p.onSubmit}
          busy={p.run.kind === "loading"}
          bodyError={p.bodyError}
          evidence={evidence}
          readOnly={p.readOnly}
          onNew={p.onNew}
        />
        <Pipeline run={p.run} />
      </aside>
      <main className="rise min-w-0 bg-bg px-8 py-6">
        <div className="mx-auto max-w-[1080px]">
          <ResultsPane run={p.run} onRetry={p.onRetry} />
        </div>
      </main>
    </div>
  );
}

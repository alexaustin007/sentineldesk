import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Tip, TipBody, TipKV, TipLine, TipTable, useTip } from "../components/Tip";
import { fmtCost, fmtSeconds, stageName } from "../lib/labels";
import { loadMetrics, type LoadedMetrics } from "../lib/metrics";
import { mostConfused } from "../lib/metricsText";
import { HEAD_NAMES, type HeadMetrics, type HeadName, type Metrics } from "../types/metrics";

const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;
const score = (x: number) => x.toFixed(2);
const int = (x: number | undefined | null) => (x == null ? "—" : Math.round(x).toLocaleString("en-US"));

// Typography (spec v2): page title 24/32 · section question 17/24 · hero 44/48 · body and table 15/24 ·
// labels 13/18 · facts value 17/24. Inter only, sentence case, no monospace.
const H2 = "text-[17px] leading-6 font-semibold text-ink";
const SECTION = "border-t border-line pt-8";
const LABEL = "text-[13px] leading-[18px] text-ink-3";

const TITLES = {
  urgent: "Does it catch urgent incidents?",
  accuracy: "How accurate is the triage?",
  sound: "Is the evaluation sound, and is it fast?",
};

/** Holdout metrics from metrics.json (UI_WORKFLOW §4.2). Falls back to the bundled sample, labelled as such. */
export function MetricsPage() {
  const [state, setState] = useState<
    { kind: "loading" } | { kind: "ready"; data: LoadedMetrics } | { kind: "error"; message: string }
  >({ kind: "loading" });
  const load = useCallback(() => {
    const ctrl = new AbortController();
    setState({ kind: "loading" });
    loadMetrics(ctrl.signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setState({ kind: "error", message: e instanceof Error ? e.message : String(e) });
      });
    return ctrl;
  }, []);
  useEffect(() => {
    const ctrl = load();
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <MetricsLoading />;
  if (state.kind === "error") return <MetricsInvalid message={state.message} onRetry={load} />;
  return <MetricsView {...state.data} />;
}

function Column({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex w-full max-w-[880px] flex-col gap-10 pb-12">{children}</div>;
}

function Title({ children }: { children: ReactNode }) {
  return <h1 className="text-[24px] leading-8 font-semibold text-ink">Triage performance{children}</h1>;
}

/** Loading: the three section titles with grey placeholder lines (no spinner). */
export function MetricsLoading() {
  return (
    <Column>
      <div aria-busy="true" aria-label="Loading metrics">
        <Title>{null}</Title>
        <div className="mt-2 h-4 w-72 rounded bg-surface-2" />
      </div>
      {["Urgent incidents", "Routing and timing"].map((t) => (
        <section key={t} className={SECTION}>
          <h2 className={H2}>{t}</h2>
          <div className="mt-4 space-y-3">
            <div className="h-4 w-1/3 rounded bg-line" />
            <div className="h-4 w-2/3 rounded bg-surface-2" />
          </div>
        </section>
      ))}
    </Column>
  );
}

/** Invalid file: an inline message under the page title, plus a Retry link. */
export function MetricsInvalid({ message, onRetry }: { message: string; onRetry: () => void }) {
  const fields = message.replace(/^metrics\.json missing or invalid:\s*/, "");
  return (
    <Column>
      <div role="alert">
        <Title>{null}</Title>
        <p className="mt-1 text-[14px] leading-5 text-ink-2">
          Metrics file is missing or invalid: {fields}{" "}
          <button type="button" onClick={onRetry} className="font-medium text-accent underline underline-offset-2 hover:opacity-80">
            Retry
          </button>
        </p>
      </div>
    </Column>
  );
}

/** Dotted-underline trigger for hover/focus tooltips: no icons, no buttons. */
function Hint({ tip, wide = false, className = "", children }: { tip: ReactNode; wide?: boolean; className?: string; children: ReactNode }) {
  return (
    <Tip wide={wide} content={tip} className={`underline decoration-dotted decoration-ink-3 underline-offset-[5px] hover:decoration-ink ${className}`}>
      {children}
    </Tip>
  );
}

type Mix = NonNullable<NonNullable<Metrics["pipeline"]>["status_mix"]>;
const share = (mix: Mix, k: keyof Mix) => mix[k] / (mix.auto_draft + mix.human_review + mix.escalate || 1);

const HEAD_LABEL: Record<HeadName, string> = { type: "Type", queue: "Queue", priority: "Priority" };

interface Col {
  key: string;
  header: string;
  /** One-line definition shown on hover/focus of the header. */
  def: string;
  value: (h: HeadMetrics) => number | undefined;
}

const COLS: Col[] = [
  { key: "acc", header: "Accuracy", def: "Share of holdout tickets labelled correctly.", value: (h) => h.accuracy },
  {
    key: "ece",
    header: "Calibration error",
    def: "Groups predictions by confidence and measures the average gap between confidence and accuracy. Closer to zero is better.",
    value: (h) => h.calibration_error,
  },
];

/** Three sections titled by the question they answer; exact numbers are one hover or focus away. */
export function MetricsView({ metrics: m, source }: LoadedMetrics) {
  const classifierOnly = m.evaluation_scope === "classifier";
  const holdout = m.split?.holdout;
  const c = m.high_priority_incident;
  const tradeoff = [...(m.escalation_tradeoff ?? [])].sort((a, b) => a.target_recall - b.target_recall);
  const ninety = tradeoff.find((r) => Math.abs(r.target_recall - 0.9) < 1e-6) ?? tradeoff[Math.floor(tradeoff.length / 2)];
  // An optional column shows only when every head has the value: no empty cells, no "N/A".
  const cols = COLS.filter((col) => HEAD_NAMES.every((k) => col.value(m.heads[k]) != null));
  const p = m.pipeline;
  const mix = p?.status_mix;
  const n = p?.tickets ?? holdout ?? null;
  const cost = fmtCost(p?.avg_cost_usd);
  const overlapNote = m.split?.leakage_detail || m.split?.leakage_check;
  const d = m.drafts;
  const draftHeadline = d
    ? d.citations_valid_rate != null
      ? `${pct(d.citations_valid_rate)} citations valid`
      : d.language_match_rate != null
        ? `${pct(d.language_match_rate)} language match`
        : d.removed_claims_rate != null
          ? `${pct(d.removed_claims_rate)} claims removed`
          : null
    : null;

  const facts: { key: string; label: string; value: string; tip: ReactNode; wide?: boolean }[] = [];
  if (holdout != null) facts.push({ key: "holdout", label: "Holdout", value: `${int(holdout)} tickets`, tip: <SplitTip m={m} /> });
  if (p?.latency_ms) facts.push({ key: "lat", label: "Median latency", value: fmtSeconds(p.latency_ms.p50), tip: <LatencyTip p={p} />, wide: true });
  if (cost) facts.push({ key: "cost", label: "Cost per ticket", value: cost, tip: <CostTip m={m} />, wide: true });
  if (draftHeadline && d) facts.push({ key: "draft", label: "Draft quality", value: draftHeadline, tip: <DraftTip d={d} /> });


  return (
    <Column>
      <div>
        <Title>{null}</Title>
        <p className="mt-1 text-[15px] leading-6 text-ink-2">
          {source === "sample" ? "Sample data" : classifierOnly ? "Classifier benchmark" : "Evaluation results"}
          {holdout != null && <> · {int(holdout)} test tickets</>}
        </p>
      </div>

      <section aria-labelledby="summary-urgent" className={SECTION}>
        <h2 id="summary-urgent" className={H2}>{classifierOnly ? "Urgent incidents identified by the classifier" : "Urgent incidents flagged for on-call"}</h2>
        <p className="num mt-3 text-[44px] leading-[48px] font-semibold text-ink">{pct(m.high_priority_incident_recall, 1)}</p>
        <p className="mt-1 text-[15px] leading-6 text-ink-2">
          {c ? <>{int(c.caught)} of {int(c.total)} urgent incidents flagged. {int(c.total - c.caught)} missed.</>
            : "Share of urgent incidents flagged for the on-call team."}
        </p>
      </section>

      {(m.heads.queue.accuracy != null || p?.latency_ms) && (
        <dl className="grid gap-6 border-t border-line pt-6 sm:grid-cols-2">
          {m.heads.queue.accuracy != null && (
            <div>
              <dt className={H2}>{classifierOnly ? "Correct team predicted" : "Sent to the right team"}</dt>
              <dd className="num mt-2 text-2xl font-semibold">{pct(m.heads.queue.accuracy, 1)}</dd>
            </div>
          )}
          {p?.latency_ms && (
            <div>
              <dt className={H2}>Typical time to triage</dt>
              <dd className="num mt-2 text-2xl font-semibold">{fmtSeconds(p.latency_ms.p50)}</dd>
              <dd className="mt-1 text-[14px] text-ink-2">Time from ticket submission to a triage decision (median).</dd>
            </div>
          )}
        </dl>
      )}

      <details className="border-t border-line pt-5">
        <summary className="cursor-pointer text-[15px] font-medium text-accent">Technical details</summary>
        <div className="mt-6 flex flex-col gap-8">
          <section aria-labelledby="m-urgent" className={SECTION}>
            <h2 id="m-urgent" className={H2}>
              {TITLES.urgent}
            </h2>
            <p className="mt-3">
              <Hint tip={<RecallTip m={m} />} className="underline-offset-[8px]">
                <span className="num text-[44px] leading-[48px] font-semibold text-ink">{pct(m.high_priority_incident_recall, 1)}</span>
              </Hint>
            </p>
            <p className="mt-1 text-[15px] leading-6 text-ink-2">
              High-priority incident recall{c ? <> · <span className="num">{int(c.caught)} of {int(c.total)}</span> {classifierOnly ? "identified" : "escalated to on-call"}</> : null}
            </p>
            {ninety && (
              <p className="mt-3 text-[15px] leading-6 text-ink">
                <Hint wide tip={<TradeoffTip rows={tradeoff} ninety={ninety} />}>
                  To catch <span className="num">{pct(ninety.target_recall)}</span> of them, <span className="num">{pct(ninety.escalation_rate)}</span> of all tickets go
                  to a human.
                </Hint>
              </p>
            )}
          </section>

          {cols.length > 0 && (
            <section aria-labelledby="m-accuracy" className={SECTION}>
              <h2 id="m-accuracy" className={H2}>
                {TITLES.accuracy}
              </h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full border-collapse text-[15px] leading-6">
                  <thead>
                    <tr>
                      <th scope="col" className="pb-2 text-left">
                        <span className="sr-only">Prediction</span>
                      </th>
                      {cols.map((col) => (
                        <th key={col.key} scope="col" className="pb-2 pl-6 text-right text-[13px] leading-[18px] font-medium text-ink-2">
                          <Hint tip={<TipBody>{col.def}</TipBody>}>{col.header}</Hint>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {HEAD_NAMES.map((k) => (
                      <HeadRow key={k} name={k} h={m.heads[k]} cols={cols} />
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {(facts.length > 0 || overlapNote || mix) && (
            <section aria-labelledby="m-sound" className={SECTION}>
              <h2 id="m-sound" className={H2}>
                {TITLES.sound}
              </h2>
              {facts.length > 0 && (
                <dl className={`mt-3 grid grid-cols-2 gap-x-6 gap-y-5 ${facts.length > 4 ? "min-[900px]:grid-cols-5" : "min-[900px]:grid-cols-4"}`}>
                  {facts.map((f) => (
                    <div key={f.key}>
                      <dt className={LABEL}>{f.label}</dt>
                      <dd>
                        <Hint wide={f.wide} tip={f.tip} className="num text-[17px] leading-6 font-medium text-ink">
                          {f.value}
                        </Hint>
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
              {overlapNote && <p className="mt-4 text-[14px] text-ink-2"><strong>Evaluation data overlap.</strong> {overlapNote}</p>}
              {mix && (
                <p className={`${facts.length > 0 ? "mt-6 " : "mt-3 "}flex flex-wrap items-baseline gap-x-4 text-[15px] leading-6`}>
                  <span className={LABEL}>Outcome mix</span>
                  <Hint tip={<MixTip mix={mix} n={n} />}>
                    <span className="num">
                      <span className="text-ok-text">{pct(share(mix, "auto_draft"))} auto-draft</span>
                      {" · "}
                      <span className="text-rev-text">{pct(share(mix, "human_review"))} human review</span>
                      {" · "}
                      <span className="text-esc-text">{pct(share(mix, "escalate"))} escalated</span>
                    </span>
                  </Hint>
                </p>
              )}
            </section>
          )}
        </div>
      </details>
    </Column>
  );
}

/** One accuracy row. The whole row is the hover/focus target for the per-class table. */
function HeadRow({ name, h, cols }: { name: HeadName; h: HeadMetrics; cols: Col[] }) {
  const { props, node } = useTip(<ClassTip name={name} h={h} />, { wide: true });
  return (
    <>
      <tr {...props} className="cursor-help border-b border-line/70 last:border-b-0 hover:bg-surface">
        <th scope="row" className="py-3 pr-6 text-left font-normal text-ink">
          <span className="underline decoration-dotted decoration-ink-3 underline-offset-[5px]">{HEAD_LABEL[name]}</span>
        </th>
        {cols.map((col) => (
          <td key={col.key} className="num py-3 pl-6 text-right text-ink">
            {score(col.value(h) as number)}
          </td>
        ))}
      </tr>
      {node}
    </>
  );
}

function RecallTip({ m }: { m: Metrics }) {
  const c = m.high_priority_incident;
  const total = m.split?.holdout;
  return (
    <TipBody>
      <TipLine>{m.evaluation_scope === "classifier" ? "Share of urgent incidents correctly classified as both high priority and Incident." : "Of holdout tickets that are priority high and type Incident, the share the gate escalated to on-call."}</TipLine>
      {c && (
        <TipKV k="Caught">
          <span className="num font-medium">
            {int(c.caught)} of {int(c.total)}
          </span>{" "}
          · <span className="num font-medium">{int(c.total - c.caught)}</span> missed
        </TipKV>
      )}
      {c?.escalation_rate != null && (
        <TipLine>
          <span className="num font-medium">{pct(c.escalation_rate)}</span> of all tickets escalated
          {total ? (
            <>
              {" "}
              (<span className="num">{int(c.escalation_rate * total)}</span> of <span className="num">{int(total)}</span>)
            </>
          ) : null}
        </TipLine>
      )}
    </TipBody>
  );
}

function TradeoffTip({ rows, ninety }: { rows: NonNullable<Metrics["escalation_tradeoff"]>; ninety: NonNullable<Metrics["escalation_tradeoff"]>[number] }) {
  return (
    <TipBody title="Escalation trade-off">
      <TipTable
        head={["Catch rate", "Sent to a human", "Precision", "Tickets"]}
        rows={rows.map((r) => ({
          key: String(r.target_recall),
          strong: r === ninety,
          cells: [pct(r.target_recall), pct(r.escalation_rate), r.precision != null ? score(r.precision) : "—", int(r.tickets_escalated)],
        }))}
      />
    </TipBody>
  );
}

function ClassTip({ name, h }: { name: HeadName; h: HeadMetrics }) {
  const rows = [...h.per_class].sort((a, b) => b.support - a.support);
  const conf = mostConfused(h);
  return (
    <TipBody title={`${HEAD_LABEL[name]}: per class`}>
      <TipTable
        head={["Class", "Precision", "Recall", "Tickets"]}
        rows={rows.map((c) => ({
          key: c.label,
          cells: [c.label, score(c.precision), score(c.recall), int(c.support)],
        }))}
      />
      {conf && (
        <span className="flex min-w-0 items-baseline gap-x-1 text-[12.5px] whitespace-nowrap">
          <span className="shrink-0">Most often confused:</span>
          <span className="min-w-0 truncate">{conf.from}</span>
          <span className="shrink-0">→</span>
          <span className="min-w-0 truncate">{conf.to}</span>
          <span className="num shrink-0">({int(conf.count)})</span>
        </span>
      )}
    </TipBody>
  );
}

function SplitTip({ m }: { m: Metrics }) {
  const s = m.split!;
  return (
    <TipBody title="Data splits">
      {s.train != null && (
        <TipKV k="Train">
          <span className="num font-medium">{int(s.train)}</span> · the classifier learns from these
        </TipKV>
      )}
      {s.knowledge_base != null && (
        <TipKV k="Knowledge base">
          <span className="num font-medium">{int(s.knowledge_base)}</span> · the retrieval index
        </TipKV>
      )}
      {s.holdout != null && (
        <TipKV k="Holdout">
          <span className="num font-medium">{int(s.holdout)}</span> · scored here, never trained on or indexed
        </TipKV>
      )}
    </TipBody>
  );
}

function LatencyTip({ p }: { p: NonNullable<Metrics["pipeline"]> }) {
  const l = p.latency_ms!;
  const stages = Object.entries(p.stage_latency_ms ?? {});
  return (
    <TipBody title="End-to-end latency">
      <TipKV k="p50">
        <span className="num font-medium">{fmtSeconds(l.p50)}</span> · half of tickets finish faster than this
      </TipKV>
      <TipKV k="p95">
        <span className="num font-medium">{fmtSeconds(l.p95)}</span> · only the slowest 5% take longer
      </TipKV>
      {stages.length > 0 && <TipTable head={["Stage (median)", "ms"]} rows={stages.map(([k, v]) => ({ key: k, cells: [stageName(k), int(v)] }))} />}
    </TipBody>
  );
}

function CostTip({ m }: { m: Metrics }) {
  const avg = m.pipeline?.avg_cost_usd ?? 0;
  const parts = Object.entries(m.pipeline?.cost_breakdown_usd ?? {});
  return (
    <TipBody title="Cost per ticket">
      {m.pipeline?.cost_basis && <TipLine>{m.pipeline.cost_basis}</TipLine>}
      {parts.length > 0 && (
        <TipTable
          head={["Stage", "USD", "Share"]}
          rows={parts.map(([k, v]) => ({ key: k, cells: [stageName(k), v.toFixed(4), avg ? pct(v / avg) : ""] }))}
        />
      )}
      <TipLine>
        About <span className="num font-medium">${(avg * 1000).toFixed(2)}</span> per 1,000 tickets.
      </TipLine>
    </TipBody>
  );
}

function MixTip({ mix, n }: { mix: Mix; n: number | null }) {
  const row = (k: keyof Mix, label: string, cls: string) => (
    <TipLine key={k}>
      <span className={`font-medium ${cls}`}>{label}</span>{" "}
      <span className="num">
        {n ? `${int(share(mix, k) * n)} of ${int(n)} · ` : ""}
        {pct(share(mix, k), 1)}
      </span>
    </TipLine>
  );
  return (
    <TipBody title="Outcome of the full pipeline">
      {row("auto_draft", "Auto-draft ready", "text-ok-text")}
      {row("human_review", "Needs human review", "text-rev-text")}
      {row("escalate", "Escalated to on-call", "text-esc-text")}
    </TipBody>
  );
}

function DraftTip({ d }: { d: NonNullable<Metrics["drafts"]> }) {
  const lines: [string, number | null][] = [
    ["Citations valid", d.citations_valid_rate],
    ["Reply language matches ticket", d.language_match_rate],
    ["Drafts with a claim removed", d.removed_claims_rate],
  ];
  return (
    <TipBody title="Draft quality (from RAG eval)">
      {lines
        .filter(([, v]) => v != null)
        .map(([k, v]) => (
          <TipKV key={k} k={k}>
            <span className="num font-medium">{pct(v as number, 1)}</span>
          </TipKV>
        ))}
    </TipBody>
  );
}

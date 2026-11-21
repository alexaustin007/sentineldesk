import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { ConfusionMatrix } from "../components/ConfusionMatrix";
import { IconCross } from "../components/Icons";
import { BarList, ScaleMarkers, StackedBar, TradeoffChart, type Segment } from "../components/MetricCharts";
import { Section } from "../components/Section";
import { fmtCost, fmtSeconds, stageName } from "../lib/labels";
import { loadMetrics, type LoadedMetrics } from "../lib/metrics";
import { HEAD_NAMES, type HeadName, type Metrics, type TradeoffRow } from "../types/metrics";

type State = { kind: "loading" } | { kind: "ready"; data: LoadedMetrics } | { kind: "error"; message: string };

const pct = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;
const score = (x: number) => x.toFixed(2);
const int = (x: number | undefined | null) => (x == null ? "—" : Math.round(x).toLocaleString("en-US"));

/** Holdout metrics from metrics.json (UI_WORKFLOW §4.2). Falls back to the bundled sample, clearly labelled. */
export function MetricsPage() {
  const [state, setState] = useState<State>({ kind: "loading" });
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

  if (state.kind === "loading")
    return (
      <div className="mx-auto grid max-w-[1120px] gap-5 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true" aria-label="Loading metrics">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl border border-line bg-surface" />
        ))}
      </div>
    );
  if (state.kind === "error")
    return (
      <section role="alert" className="relative mx-auto max-w-[1120px] overflow-hidden rounded-xl border border-line bg-surface py-6 pr-6 pl-8">
        <span aria-hidden className="absolute inset-y-0 left-0 w-1.5 bg-ink-3" />
        <p className="label">Metrics did not load</p>
        <p className="mt-1 text-[20px] font-semibold text-ink">The metrics file is not in the expected shape</p>
        <p className="mt-1.5 text-[15px] text-ink-2">{state.message}</p>
        <div className="mt-5 flex items-center gap-4">
          <button
            type="button"
            onClick={load}
            className="h-10 rounded-lg border border-field bg-surface px-4 text-[14.5px] font-semibold text-ink hover:border-ink-2"
          >
            Retry
          </button>
          <span className="mono text-[13px] text-ink-3">BAD_METRICS</span>
        </div>
      </section>
    );
  return <MetricsView {...state.data} />;
}

const HEAD_TITLE: Record<HeadName, { title: string; noun: string }> = {
  type: { title: "Ticket type", noun: "types" },
  queue: { title: "Queue routing", noun: "queues" },
  priority: { title: "Priority", noun: "priority levels" },
};

type PanelId =
  | "recall"
  | `f1-${HeadName}`
  | `trade-${number}`
  | "status"
  | "latency"
  | "cost"
  | "split";

/**
 * Calm first view: each reading is just a title and a number. Every reading has its own
 * "More info" control that opens a details panel attached to it (one at a time, Esc closes).
 */
export function MetricsView({ metrics: m, source }: LoadedMetrics) {
  const [open, setOpen] = useState<PanelId | null>(null);
  const triggers = useRef<Partial<Record<PanelId, HTMLButtonElement | null>>>({});
  const toggle = (id: PanelId) => setOpen((o) => (o === id ? null : id));
  const close = useCallback(() => {
    setOpen((o) => {
      if (o) triggers.current[o]?.focus();
      return null;
    });
  }, []);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);

  // Text "More info" only on the four headline tiles; elsewhere an icon button (32 px hit area).
  const info = (id: PanelId, label: string, compact = false) => (
    <MoreInfo id={id} label={label} compact={compact} open={open === id} onToggle={() => toggle(id)} refFn={(el) => (triggers.current[id] = el)} />
  );
  const panel = (ids: PanelId[], within: RefObject<HTMLElement | null>) =>
    open && ids.includes(open) ? (
      <InfoPanel id={open} title={panelTitle(open, tradeoff)} trigger={triggers.current[open] ?? null} within={within} onClose={close}>
        <PanelBody id={open} m={m} />
      </InfoPanel>
    ) : null;

  const tilesRef = useRef<HTMLDivElement>(null);
  const tradeRef = useRef<HTMLDivElement>(null);
  const pipeRef = useRef<HTMLDivElement>(null);
  const footRef = useRef<HTMLDivElement>(null);
  const tradeoff = [...(m.escalation_tradeoff ?? [])].sort((a, b) => a.target_recall - b.target_recall);
  const ninety = tradeoff.find((r) => Math.abs(r.target_recall - 0.9) < 1e-6) ?? tradeoff[Math.floor(tradeoff.length / 2)];
  const p = m.pipeline;
  const mix = p?.status_mix;
  const cost = fmtCost(p?.avg_cost_usd);
  const tileIds: PanelId[] = ["recall", "f1-type", "f1-queue", "f1-priority"];

  return (
    <div className="mx-auto flex max-w-[1120px] flex-col gap-8 pb-10">
      <div>
        <h1 className="text-[22px] font-semibold text-ink">Model metrics</h1>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 text-[14.5px] text-ink-3">
          {source === "sample" && (
            <>
              <span aria-hidden className="h-2 w-2 rounded-full bg-amber" />
              <span role="note">
                <span className="font-medium text-ink-2">Sample data:</span> real metrics not generated yet
              </span>
              <span aria-hidden>·</span>
            </>
          )}
          <span>
            Holdout set of <span className="num">{int(m.split?.holdout)}</span> tickets the model never saw
          </span>
        </p>
      </div>

      {/* Headline tiles: title + number + More info. The open tile stays highlighted above its panel. */}
      <div ref={tilesRef} className="flex flex-col gap-4">
        <div className="grid gap-x-5 gap-y-2 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div className="sm:col-span-2 lg:col-span-1 lg:row-start-2">
            <Tile big title="Urgent incidents caught" value={pct(m.high_priority_incident_recall)} active={open === "recall"}>
              {info("recall", "Urgent incidents caught")}
            </Tile>
          </div>
          {/* Unit said once for the three F1 tiles. */}
          <p className="mt-3 text-[13.5px] font-medium text-ink-3 sm:col-span-2 lg:col-span-3 lg:col-start-2 lg:row-start-1 lg:mt-0">
            Accuracy by label · macro-F1 (0–1)
          </p>
          {HEAD_NAMES.map((k) => (
            <Tile key={k} className="lg:row-start-2" title={HEAD_TITLE[k].title} value={score(m.heads[k].macro_f1)} active={open === `f1-${k}`}>
              {info(`f1-${k}`, HEAD_TITLE[k].title)}
            </Tile>
          ))}
        </div>
        {panel(tileIds, tilesRef)}
      </div>

      {ninety && (
        <Section label="Escalation trade-off">
          <div ref={tradeRef} className="flex flex-col gap-4">
            <div className="grid items-start gap-6 md:grid-cols-[minmax(0,1.1fr)_minmax(320px,1fr)]">
              <p className="text-[18px] leading-snug text-ink">
                To catch <span className="num font-semibold">{pct(ninety.target_recall)}</span> of urgent incidents,{" "}
                <span className="num font-semibold">{pct(ninety.escalation_rate)}</span> of tickets go to a human.
              </p>
              <div className="text-[14.5px]">
                <div className="grid grid-cols-[92px_minmax(0,1fr)_48px_32px] gap-x-3 pb-1.5 text-[13.5px] font-medium text-ink-3">
                  <span>Catch rate</span>
                  <span className="col-span-2 text-right">Sent to a human</span>
                  <span />
                </div>
                {tradeoff.map((r, i) => {
                  const id = `trade-${i}` as PanelId;
                  return (
                    <div
                      key={r.target_recall}
                      data-reading
                      className={`grid grid-cols-[92px_minmax(0,1fr)_48px_32px] items-center gap-x-3 rounded-md py-1 ${open === id ? "bg-accent-soft" : ""} ${r === ninety ? "font-semibold" : ""}`}
                    >
                      <span className="num pl-1 text-ink">{pct(r.target_recall)}</span>
                      <span className="h-1.5 rounded-full bg-bar-track">
                        <span className="block h-full rounded-full bg-bar" style={{ width: `${r.escalation_rate * 100}%` }} />
                      </span>
                      <span className="num text-right text-ink">{pct(r.escalation_rate)}</span>
                      {info(id, `${pct(r.target_recall)} catch rate`, true)}
                    </div>
                  );
                })}
              </div>
            </div>
            {panel(
              tradeoff.map((_, i) => `trade-${i}` as PanelId),
              tradeRef,
            )}
          </div>
        </Section>
      )}

      {p && (mix || p.latency_ms || cost) && (
        <div ref={pipeRef} className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-x-10 gap-y-3 text-[14.5px] text-ink-2">
            <span className="font-medium text-ink">Pipeline on the holdout set</span>
            {mix && (
              <Reading active={open === "status"}>
                <span aria-hidden className="flex h-2.5 w-36 overflow-hidden rounded-full">
                  <span className="bg-ok" style={{ width: `${share(mix, "auto_draft") * 100}%` }} />
                  <span className="bg-rev" style={{ width: `${share(mix, "human_review") * 100}%` }} />
                  <span className="bg-esc" style={{ width: `${share(mix, "escalate") * 100}%` }} />
                </span>
                <span className="num">{pct(share(mix, "auto_draft"))} auto-draft</span>
                {info("status", "Status mix", true)}
              </Reading>
            )}
            {p.latency_ms && (
              <Reading active={open === "latency"}>
                <span className="num">{fmtSeconds(p.latency_ms.p50)} typical</span>
                {info("latency", "Latency", true)}
              </Reading>
            )}
            {cost && (
              <Reading active={open === "cost"}>
                <span className="num">{cost} per ticket</span>
                {info("cost", "Cost", true)}
              </Reading>
            )}
          </div>
          {panel(["status", "latency", "cost"], pipeRef)}
        </div>
      )}

      <div ref={footRef} className="flex flex-col gap-4">
        <footer className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[13px] text-ink-3">
          {m.split && (
            <Reading active={open === "split"}>
              <span className="num">
                Train {int(m.split.train)} · knowledge base {int(m.split.knowledge_base)} · holdout {int(m.split.holdout)}
              </span>
              {info("split", "Split sizes", true)}
            </Reading>
          )}
          {m.model && <span>Model: {m.model}</span>}
          {m.dataset && <span>Dataset: {m.dataset}</span>}
          {m.generated_at && <span className="num">Generated {fmtDate(m.generated_at)}</span>}
        </footer>
        {panel(["split"], footRef)}
      </div>
    </div>
  );
}

const share = (mix: NonNullable<NonNullable<Metrics["pipeline"]>["status_mix"]>, k: "auto_draft" | "human_review" | "escalate") =>
  mix[k] / (mix.auto_draft + mix.human_review + mix.escalate || 1);

function fmtDate(iso: string) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Tile({
  title,
  value,
  active,
  big = false,
  className = "",
  children,
}: {
  title: string;
  value: string;
  active: boolean;
  big?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      data-reading
      className={`flex h-full flex-col rounded-xl border bg-surface px-6 pt-5 pb-3 transition-colors ${className} ${
        active ? "border-accent shadow-[0_0_0_1px_var(--accent)]" : big ? "border-line-strong shadow-[0_1px_3px_rgb(0_0_0/0.06)]" : "border-line"
      }`}
    >
      <p className="text-[15px] font-medium text-ink-2">{title}</p>
      <p className={`num mt-2 font-semibold text-ink ${big ? "text-[44px] leading-none" : "text-[32px] leading-none"}`}>{value}</p>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function Reading({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <span data-reading className={`-mx-2 flex items-center gap-3 rounded-lg px-2 ${active ? "bg-accent-soft" : ""}`}>
      {children}
    </span>
  );
}

function InfoIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5">
      <circle cx="8" cy="8" r="6.25" />
      <path d="M8 7.2v3.6M8 5.1v.1" strokeLinecap="round" />
    </svg>
  );
}

/** Quiet "More info" control; the panel it opens is attached to this reading. */
function MoreInfo({
  id,
  label,
  open,
  compact = false,
  onToggle,
  refFn,
}: {
  id: PanelId;
  label: string;
  open: boolean;
  compact?: boolean;
  onToggle: () => void;
  refFn: (el: HTMLButtonElement | null) => void;
}) {
  return (
    <button
      ref={refFn}
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-controls={`panel-${id}`}
      aria-label={`${open ? "Hide" : "More"} info: ${label}`}
      className={`inline-flex h-8 items-center rounded-md text-[13.5px] font-medium whitespace-nowrap ${
        compact ? "w-8 justify-center" : "-mx-2 gap-1.5 px-2"
      } ${open ? "text-accent" : "text-ink-3 hover:bg-surface-2 hover:text-ink"}`}
    >
      <InfoIcon />
      {!compact && <span>{open ? "Less info" : "More info"}</span>}
    </button>
  );
}

/** Details panel opened from a reading; a small pointer aims at the trigger so it's clear what it explains. */
function InfoPanel({
  id,
  title,
  trigger,
  within,
  onClose,
  children,
}: {
  id: PanelId;
  title: string;
  trigger: HTMLElement | null;
  within: RefObject<HTMLElement | null>;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const [caret, setCaret] = useState<number | null>(null);
  useLayoutEffect(() => {
    const place = () => {
      const panel = ref.current?.getBoundingClientRect();
      const t = (trigger?.closest("[data-reading]") ?? trigger)?.getBoundingClientRect();
      if (!panel || !t) return setCaret(null);
      setCaret(Math.min(panel.width - 24, Math.max(24, t.left + t.width / 2 - panel.left)));
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [trigger, within, id]);
  return (
    <section
      ref={ref}
      id={`panel-${id}`}
      aria-label={`Details: ${title}`}
      className="rise relative rounded-xl border border-accent/60 bg-surface px-6 pt-5 pb-6 shadow-[0_4px_16px_rgb(0_0_0/0.06)]"
    >
      {caret != null && (
        <span
          aria-hidden
          className="absolute -top-[7px] h-3 w-3 rotate-45 border-t border-l border-accent/60 bg-surface"
          style={{ left: caret - 6 }}
        />
      )}
      <div className="flex items-start justify-between gap-4">
        <h2 className="heading">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="-mt-1 -mr-2 grid h-8 w-8 place-items-center rounded-md text-ink-3 hover:bg-surface-2 hover:text-ink"
        >
          <IconCross />
        </button>
      </div>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function panelTitle(id: PanelId, tradeoff: TradeoffRow[]): string {
  if (id.startsWith("trade-")) {
    const r = tradeoff[Number(id.slice(6))];
    return r ? `At a ${pct(r.target_recall)} catch rate` : "Trade-off";
  }
  return PANEL_TITLE[id] ?? "Details";
}

const PANEL_TITLE: Partial<Record<string, string>> = {
  recall: "High-priority incident recall",
  "f1-type": "Macro-F1",
  "f1-queue": "Macro-F1",
  "f1-priority": "Macro-F1",
  status: "Status mix",
  latency: "Latency",
  cost: "Cost per ticket",
  split: "Splits and leakage check",
};

function Definition({ children }: { children: ReactNode }) {
  return <p className="max-w-[72ch] text-[15px] leading-relaxed text-ink-2">{children}</p>;
}

function SubHead({ children }: { children: ReactNode }) {
  return <h3 className="mt-6 mb-2.5 text-[15px] font-semibold text-ink">{children}</h3>;
}

function PanelBody({ id, m }: { id: PanelId; m: Metrics }) {
  if (id === "recall") return <RecallPanel m={m} />;
  if (id.startsWith("f1-")) return <F1Panel head={id.slice(3) as HeadName} m={m} />;
  if (id.startsWith("trade-")) {
    const rows = [...(m.escalation_tradeoff ?? [])].sort((a, b) => a.target_recall - b.target_recall);
    const r = rows[Number(id.slice(6))];
    return r ? <TradeoffPanel r={r} m={m} /> : null;
  }
  if (id === "status") return <StatusPanel m={m} />;
  if (id === "latency") return <LatencyPanel m={m} />;
  if (id === "cost") return <CostPanel m={m} />;
  return <SplitPanel m={m} />;
}

function RecallPanel({ m }: { m: Metrics }) {
  const c = m.high_priority_incident;
  const missed = c ? c.total - c.caught : 0;
  return (
    <>
      <Definition>
        Of the holdout tickets labelled <strong className="font-semibold text-ink">priority = high</strong> and{" "}
        <strong className="font-semibold text-ink">type = Incident</strong>, the share the gate escalated to the on-call engineer. A miss means an
        urgent outage waits in a normal queue, so this is the number the gate is tuned for.
      </Definition>
      <div className="mt-5 grid gap-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(300px,1fr)]">
        <div>
          {c ? (
            <>
              <p className="text-[16px] text-ink">
                <span className="num font-semibold">{int(c.caught)}</span> of <span className="num font-semibold">{int(c.total)}</span> caught,{" "}
                <span className="num font-semibold">{int(missed)}</span> missed
              </p>
              <div className="mt-3">
                <StackedBar
                  parts={[
                    { key: "caught", label: "Caught (escalated)", value: c.caught, cls: "bg-ok", tip: `${int(c.caught)} urgent incidents escalated` },
                    { key: "missed", label: "Missed", value: missed, cls: "bg-esc", tip: `${int(missed)} urgent incidents not escalated` },
                  ]}
                  legend={false}
                />
              </div>
              {c.escalation_rate != null && (
                <p className="mt-5 text-[15px] text-ink-2">
                  At this setting <span className="num font-semibold text-ink">{pct(c.escalation_rate)}</span> of all tickets are escalated
                  {m.split?.holdout ? (
                    <>
                      {" "}
                      (<span className="num">{int(c.escalation_rate * m.split.holdout)}</span> of <span className="num">{int(m.split.holdout)}</span>)
                    </>
                  ) : null}
                  .
                </p>
              )}
            </>
          ) : (
            <p className="text-[15px] text-ink-2">Recall {pct(m.high_priority_incident_recall, 1)}. Counts not in this metrics file.</p>
          )}
        </div>
        {!!m.escalation_tradeoff?.length && (
          <div>
            <p className="mb-1 text-[14px] font-medium text-ink-2">Share of tickets escalated for each catch rate</p>
            <TradeoffChart
              rows={m.escalation_tradeoff}
              current={c?.escalation_rate != null ? { recall: m.high_priority_incident_recall, rate: c.escalation_rate } : undefined}
            />
          </div>
        )}
      </div>
    </>
  );
}

function F1Panel({ head, m }: { head: HeadName; m: Metrics }) {
  const h = m.heads[head];
  const rows = [...h.per_class].sort((a, b) => b.support - a.support);
  const label = HEAD_TITLE[head];
  return (
    <>
      <Definition>
        Macro-F1 is the unweighted mean of per-class F1 across all {h.labels.length} {label.noun}, so a small class counts as much as a large one. F1
        balances precision (predictions that were right) and recall (true tickets that were found).
        {h.accuracy != null && (
          <>
            {" "}
            Plain accuracy is <span className="num font-medium text-ink">{pct(h.accuracy, 1)}</span>.
          </>
        )}
      </Definition>

      <SubHead>F1 by class</SubHead>
      <BarList
        headers={{ value: "F1", sub: "Tickets" }}
        rows={rows.map((c) => ({
          key: c.label,
          label: c.label,
          value: c.f1,
          max: 1,
          display: score(c.f1),
          sub: int(c.support),
          weak: c.f1 < 0.6,
          tip: `${c.label}: F1 ${score(c.f1)}${c.f1 < 0.6 ? " (below 0.60)" : ""} · ${int(c.support)} tickets`,
        }))}
      />

      <SubHead>Confusion matrix</SubHead>
      <ConfusionMatrix head={h} bare />

      <SubHead>Precision and recall by class</SubHead>
      <PerClassTable head={head} m={m} />
    </>
  );
}

function PerClassTable({ head, m }: { head: HeadName; m: Metrics }) {
  const rows = [...m.heads[head].per_class].sort((a, b) => b.support - a.support);
  const th = "px-3 pb-2 text-right text-[13.5px] font-medium text-ink-3";
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[14.5px]">
        <thead>
          <tr>
            <th className="pr-3 pb-2 text-left text-[13.5px] font-medium text-ink-3">Label</th>
            <th className={th}>Precision</th>
            <th className={th}>Recall</th>
            <th className={th}>F1</th>
            <th className={`${th} pr-0`}>Tickets</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.label} className="hover:bg-surface-2">
              <td className="py-2 pr-3 text-ink">{c.label}</td>
              <td className="num px-3 text-right text-ink-2">{score(c.precision)}</td>
              <td className="num px-3 text-right text-ink-2">{score(c.recall)}</td>
              <td className={`num px-3 text-right ${c.f1 < 0.6 ? "font-semibold text-amber" : "font-medium text-ink"}`}>{score(c.f1)}</td>
              <td className="num py-2 pl-3 text-right text-ink-3">{int(c.support)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TradeoffPanel({ r, m }: { r: TradeoffRow; m: Metrics }) {
  const total = m.split?.holdout ?? null;
  const escalated = r.tickets_escalated ?? (total ? Math.round(r.escalation_rate * total) : null);
  const urgentTotal = m.high_priority_incident?.total ?? null;
  const caught = urgentTotal != null ? Math.round(r.target_recall * urgentTotal) : r.precision != null && escalated != null ? Math.round(r.precision * escalated) : null;
  const falseAlarms = caught != null && escalated != null ? Math.max(0, escalated - caught) : null;
  const parts: Segment[] | null =
    total && escalated != null && caught != null && falseAlarms != null
      ? [
          { key: "caught", label: "Urgent, escalated", value: caught, cls: "bg-ok", tip: `${int(caught)} urgent incidents escalated` },
          { key: "extra", label: "Escalated, not urgent", value: falseAlarms, cls: "bg-bar", tip: `${int(falseAlarms)} non-urgent tickets also escalated` },
          { key: "rest", label: "Not escalated", value: total - escalated, cls: "bg-line-strong", tip: `${int(total - escalated)} tickets handled normally` },
        ]
      : null;
  return (
    <>
      <Definition>
        Tuning the gate to catch <span className="num font-semibold text-ink">{pct(r.target_recall)}</span> of urgent incidents sends{" "}
        <span className="num font-semibold text-ink">{pct(r.escalation_rate)}</span> of all tickets to a human
        {escalated != null && (
          <>
            {" "}
            (<span className="num">{int(escalated)}</span> tickets)
          </>
        )}
        .
        {r.precision != null && (
          <>
            {" "}
            Precision is <span className="num font-semibold text-ink">{score(r.precision)}</span>: {pct(r.precision)} of escalated tickets really are urgent
            incidents.
          </>
        )}
        {urgentTotal != null && caught != null && (
          <>
            {" "}
            It misses <span className="num font-semibold text-ink">{int(urgentTotal - caught)}</span> of <span className="num">{int(urgentTotal)}</span>.
          </>
        )}
      </Definition>
      {parts && (
        <div className="mt-5">
          <p className="mb-2 text-[14px] font-medium text-ink-2">All {int(total)} holdout tickets at this setting</p>
          <StackedBar parts={parts} />
        </div>
      )}
    </>
  );
}

const STATUS_MEANING = {
  auto_draft: "A grounded reply was drafted and no gate rule fired.",
  human_review: "Low confidence, no close precedent, a guardrail hit or a verifier fix.",
  escalate: "High-priority incidents, paged before any drafting.",
};

function StatusPanel({ m }: { m: Metrics }) {
  const mix = m.pipeline?.status_mix;
  if (!mix) return null;
  const n = m.pipeline?.tickets ?? m.split?.holdout ?? 0;
  const count = (k: keyof typeof STATUS_MEANING) => (n ? Math.round(share(mix, k) * n) : Math.round(share(mix, k) * 1000) / 10);
  const parts: Segment[] = [
    { key: "a", label: "Auto-draft ready", value: count("auto_draft"), cls: "bg-ok", tip: `Auto-draft ready: ${pct(share(mix, "auto_draft"), 1)}` },
    { key: "r", label: "Needs human review", value: count("human_review"), cls: "bg-rev", tip: `Needs human review: ${pct(share(mix, "human_review"), 1)}` },
    { key: "e", label: "Escalate to on-call engineer", value: count("escalate"), cls: "bg-esc", tip: `Escalate: ${pct(share(mix, "escalate"), 1)}` },
  ];
  return (
    <>
      <Definition>
        How the full pipeline (classifier, retrieval, gate, drafting and verification) decided on {n ? <span className="num">{int(n)}</span> : "the"}{" "}
        holdout tickets.
      </Definition>
      <div className="mt-5">
        <StackedBar parts={parts} height="h-5" legend={false} />
      </div>
      <dl className="mt-5 grid gap-4 text-[14.5px] md:grid-cols-3">
        {(["auto_draft", "human_review", "escalate"] as const).map((k, i) => (
          <div key={k}>
            <dt className="flex items-center gap-2 font-medium text-ink">
              <span aria-hidden className={`h-2.5 w-2.5 rounded-[3px] ${parts[i].cls}`} />
              {parts[i].label}
              <span className="num font-normal text-ink-2">
                {int(parts[i].value)} · {pct(share(mix, k))}
              </span>
            </dt>
            <dd className="mt-0.5 text-ink-2">{STATUS_MEANING[k]}</dd>
          </div>
        ))}
      </dl>
    </>
  );
}

function LatencyPanel({ m }: { m: Metrics }) {
  const l = m.pipeline?.latency_ms;
  if (!l) return null;
  const stages = Object.entries(m.pipeline?.stage_latency_ms ?? {});
  const maxStage = Math.max(1, ...stages.map(([, v]) => v));
  return (
    <>
      <Definition>
        End-to-end time from submitting a ticket to the final decision. <strong className="font-semibold text-ink">p50</strong> (median): half of
        tickets finish faster than {fmtSeconds(l.p50)}. <strong className="font-semibold text-ink">p95</strong>: 95% finish within {fmtSeconds(l.p95)};
        only the slowest 5% take longer.
      </Definition>
      <ScaleMarkers
        max={l.p95 * 1.15}
        marks={[
          { label: "p50", value: l.p50, display: fmtSeconds(l.p50) },
          { label: "p95", value: l.p95, display: fmtSeconds(l.p95) },
        ]}
      />
      {stages.length > 0 && (
        <>
          <SubHead>Median per stage</SubHead>
          <BarList
            labelWidth="minmax(140px, 180px)"
            headers={{ value: "ms" }}
            rows={stages.map(([k, v]) => ({
              key: k,
              label: stageName(k),
              value: v,
              max: maxStage,
              display: Math.round(v).toLocaleString("en-US"),
              tip: `${stageName(k)}: ${Math.round(v)} ms median`,
            }))}
          />
          <p className="mt-2 text-[13px] text-ink-3">Median over the tickets where each stage ran; adversarial review only runs on the deep route.</p>
        </>
      )}
    </>
  );
}

function CostPanel({ m }: { m: Metrics }) {
  const avg = m.pipeline?.avg_cost_usd;
  if (avg == null) return null;
  const parts = Object.entries(m.pipeline?.cost_breakdown_usd ?? {});
  const max = Math.max(...parts.map(([, v]) => v), 0) || 1;
  return (
    <>
      <Definition>
        Average LLM spend per ticket: <span className="num font-semibold text-ink">{fmtCost(avg)}</span>, or about{" "}
        <span className="num font-semibold text-ink">${(avg * 1000).toFixed(2)}</span> per 1,000 tickets. {m.pipeline?.cost_basis ?? ""}
      </Definition>
      {parts.length > 0 && (
        <>
          <SubHead>By stage, per ticket</SubHead>
          <BarList
            labelWidth="minmax(140px, 180px)"
            headers={{ value: "USD", sub: "Share" }}
            rows={parts.map(([k, v]) => ({
              key: k,
              label: stageName(k),
              value: v,
              max,
              display: v.toFixed(4),
              sub: pct(v / avg),
              tip: `${stageName(k)}: ${fmtCost(v)} per ticket`,
            }))}
          />
        </>
      )}
    </>
  );
}

function SplitPanel({ m }: { m: Metrics }) {
  const s = m.split;
  if (!s) return null;
  const sameRows = s.train != null && s.knowledge_base === s.train;
  const parts: Segment[] = [
    { key: "train", label: sameRows ? "Train + knowledge base" : "Train", value: s.train ?? 0, cls: "bg-bar", tip: `${int(s.train)} tickets for training` },
    ...(!sameRows && s.knowledge_base
      ? [{ key: "kb", label: "Knowledge base", value: s.knowledge_base, cls: "bg-ink-3", tip: `${int(s.knowledge_base)} tickets indexed for retrieval` }]
      : []),
    { key: "hold", label: "Holdout", value: s.holdout ?? 0, cls: "bg-line-strong", tip: `${int(s.holdout)} tickets scored here, never indexed` },
  ];
  return (
    <>
      <Definition>
        The classifier is trained on the train split, and retrieval searches the knowledge base{sameRows ? " (the same rows)" : ""}. Every number on this
        page is measured on the holdout split, which is never trained on or indexed.
      </Definition>
      <div className="mt-5">
        <StackedBar parts={parts} />
      </div>
      {(s.leakage_check || s.leakage_detail) && (
        <>
          <SubHead>Leakage check</SubHead>
          {s.leakage_check && <p className="text-[15px] text-ink">{s.leakage_check}.</p>}
          {s.leakage_detail && <p className="mt-1 max-w-[72ch] text-[14.5px] leading-relaxed text-ink-2">{s.leakage_detail}</p>}
        </>
      )}
    </>
  );
}


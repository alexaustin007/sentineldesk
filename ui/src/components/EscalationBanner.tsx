import { useState } from "react";
import { fmtCost, fmtSeconds, gateChecks, langCode, normalizeStatus, reasonTag, STATUS_TEXT, thresholdsOf } from "../lib/labels";
import type { EscalationStatus, TriageResponse } from "../types/triage";
import { IconCheck, IconChevron, IconCross } from "./Icons";

// One saturated colour per status; whichever banner shows is the only full-strength status colour on screen (B1).
const TONE: Record<EscalationStatus, { tint: string; stripe: string; text: string }> = {
  auto_draft: { tint: "bg-ok-tint", stripe: "bg-ok", text: "text-ok-text" },
  human_review: { tint: "bg-rev-tint", stripe: "bg-rev", text: "text-rev-text" },
  escalate: { tint: "bg-esc-tint", stripe: "bg-esc", text: "text-esc-text" },
};

function Badge({ status }: { status: EscalationStatus }) {
  const svg = { viewBox: "0 0 16 16", width: 16, height: 16, fill: "none", stroke: "currentColor", strokeWidth: 2.2, strokeLinecap: "round" as const };
  return (
    <span aria-hidden className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full ${TONE[status].stripe} text-white`}>
      {status === "escalate" ? (
        <svg {...svg}>
          <path d="M8 3.5v5.5M8 12.2v.3" />
        </svg>
      ) : status === "human_review" ? (
        <svg {...svg}>
          <circle cx="7" cy="7" r="3.6" />
          <path d="M9.8 9.8l2.7 2.7" />
        </svg>
      ) : (
        <svg {...svg} strokeLinejoin="round">
          <path d="M3.5 8.5l3 3 6-6.5" />
        </svg>
      )}
    </span>
  );
}

/**
 * The decision. Full width; reason messages sit right under the status (C3) and are
 * always rendered exactly as the backend sent them. `code` only adds a small tag.
 */
export function EscalationBanner({ res }: { res: TriageResponse }) {
  const status = normalizeStatus(res.escalation?.status);
  const escalated = status === "escalate";
  const [whyOpen, setWhyOpen] = useState(status !== "auto_draft");
  const [ackAt, setAckAt] = useState<Date | null>(null);
  const tone = TONE[status];

  const reasons = res.escalation?.reasons ?? [];
  const fallbackLine =
    status === "auto_draft"
      ? `No escalation rule triggered${res.draft ? "" : " · no draft returned"}`
      : status === "human_review"
        ? "Held for human review (no reason given)"
        : "Escalated by the gate (no reason given)";
  const evidence = [res.guardrails?.prompt_injection?.evidence, res.guardrails?.unsupported_request?.evidence].filter(
    (e): e is string => !!e,
  );
  const unique = [...new Set(evidence)];
  const route = res.route?.path && res.route.path !== "none" ? res.route.path : null;
  const cost = fmtCost(res.usage?.estimated_cost_usd);

  return (
    <section aria-label="Escalation decision" className="relative overflow-hidden rounded-lg border border-line bg-surface">
      <span aria-hidden className={`absolute inset-y-0 left-0 w-1.5 ${tone.stripe}`} />
      <div className={`${tone.tint} pl-6`}>
        <div className="flex items-start gap-4 py-4 pr-5">
          <Badge status={status} />
          <div className="min-w-0 flex-1">
            <p className={`text-[20px] leading-tight font-semibold tracking-[-0.01em] ${tone.text}`} role="status">
              {STATUS_TEXT[status]}
            </p>
            {reasons.length ? (
              <ul className="mt-1.5 space-y-1">
                {reasons.map((r, i) => {
                  const tag = reasonTag(r.code);
                  return (
                    <li key={i} className="flex items-baseline gap-2 text-[14.5px] font-medium text-ink">
                      {tag && (
                        <span className="num shrink-0 rounded-[3px] border border-field bg-surface px-1.5 py-px text-[11px] font-normal text-ink-2">
                          {tag}
                        </span>
                      )}
                      <span>{r.message}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-1 text-[14.5px] font-medium text-ink">{fallbackLine}</p>
            )}
            {escalated && res.classification?.queue?.label && (
              <p className="mt-1 text-[13.5px] text-ink-2">Paging {res.classification.queue.label} on-call</p>
            )}
            {unique.map((e) => (
              <p key={e} className="mt-2 border-l-2 border-line-strong pl-2.5 text-[13.5px] text-ink-2 italic">
                “{e}”
              </p>
            ))}
          </div>
          {escalated &&
            (ackAt ? (
              <p className="num shrink-0 pt-1.5 text-[12px] text-ink-2">
                Acknowledged by operator · {ackAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
              </p>
            ) : (
              <button
                type="button"
                onClick={() => setAckAt(new Date())}
                className="h-8 shrink-0 rounded-md border border-field bg-surface px-3 text-[13px] font-medium text-ink hover:border-ink-2"
              >
                Acknowledge
              </button>
            ))}
        </div>
        <div className="flex flex-wrap items-center gap-x-4 border-t border-line py-1.5 pr-3 text-[12.5px] text-ink-2">
          <span className="num">
            <span className="text-ink-3">lang</span> {langCode(res.input?.language_detected)}
            {res.input?.language_supported === false && <span className="text-ink-3"> (unsupported)</span>}
          </span>
          {route && (
            <span className="num">
              <span className="text-ink-3">route</span> {route}
            </span>
          )}
          <span className="num">
            <span className="text-ink-3">end-to-end</span> {fmtSeconds(res.latency_ms?.total ?? 0)}
          </span>
          {cost && (
            <span className="num" title={`${res.usage?.total_tokens ?? 0} tokens`}>
              {cost}
            </span>
          )}
          <button
            type="button"
            onClick={() => setWhyOpen((o) => !o)}
            aria-expanded={whyOpen}
            className="ml-auto flex h-8 items-center gap-1.5 rounded px-2 font-medium text-ink hover:bg-surface/60"
          >
            Why? <IconChevron open={whyOpen} />
          </button>
        </div>
      </div>
      {whyOpen && <WhyChecklist res={res} />}
    </section>
  );
}

function WhyChecklist({ res }: { res: TriageResponse }) {
  const checks = gateChecks(res);
  const { t, fallback } = thresholdsOf(res);
  return (
    <div className="border-t border-line py-3 pr-5 pl-6">
      <h3 className="label mb-1.5">Why · gate checks</h3>
      <ul className="text-[13px]">
        {checks.map((c) => (
          <li key={c.code} className="grid min-h-7 grid-cols-[18px_minmax(0,1fr)_minmax(0,1.2fr)] items-center gap-2">
            {c.pass ? <IconCheck className="text-ink-3" /> : <IconCross className="text-tone-high" />}
            <span className={c.pass ? "text-ink-2" : "font-semibold text-ink"}>{c.label}</span>
            <span className={`num truncate text-right text-[12px] ${c.pass ? "text-ink-3" : "text-ink"}`} title={c.value}>
              {c.value}
            </span>
          </li>
        ))}
      </ul>
      {fallback && (
        <p className="num mt-1 text-[12px] text-amber">
          thresholds missing from response · using defaults {t.confidence.toFixed(2)} / {t.similarity.toFixed(2)}
        </p>
      )}
    </div>
  );
}

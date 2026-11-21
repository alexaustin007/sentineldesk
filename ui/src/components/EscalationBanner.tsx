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
  // Collapsed in every state: the reason line already says why (calm on first open).
  const [whyOpen, setWhyOpen] = useState(false);
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
    <section aria-label="Escalation decision" className="relative overflow-hidden rounded-xl border border-line bg-surface">
      <span aria-hidden className={`absolute inset-y-0 left-0 w-1.5 ${tone.stripe}`} />
      <div className={`${tone.tint} py-5 pr-6 pl-7`}>
        <div className="flex items-start gap-4">
          <Badge status={status} />
          <div className="min-w-0 flex-1">
            <p className={`text-[22px] leading-tight font-semibold ${tone.text}`} role="status">
              {STATUS_TEXT[status]}
            </p>
            {reasons.length ? (
              <ul className="mt-2 space-y-1.5">
                {reasons.map((r, i) => {
                  const tag = reasonTag(r.code);
                  return (
                    <li key={i} className="flex items-baseline gap-2.5 text-[16px] leading-snug text-ink">
                      {tag && (
                        <span className="shrink-0 rounded-md bg-surface px-2 py-0.5 text-[12.5px] font-medium text-ink-2">{tag}</span>
                      )}
                      <span>{r.message}</span>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-2 text-[16px] text-ink">{fallbackLine}</p>
            )}
            {escalated && res.classification?.queue?.label && (
              <p className="mt-1.5 text-[14.5px] text-ink-2">Paging {res.classification.queue.label} on-call</p>
            )}
            {unique.map((e) => (
              <p key={e} className="mt-3 border-l-2 border-line-strong pl-3 text-[14.5px] text-ink-2 italic">
                “{e}”
              </p>
            ))}
            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-[14px] text-ink-2">
              {!res.input?.language_missing && (
                <span>
                  <span className="mono">{langCode(res.input?.language_detected)}</span>
                  {res.input?.language_supported === false && <span className="text-ink-3"> (unsupported)</span>}
                </span>
              )}
              {route && <span>{route} route</span>}
              <span className="num">{fmtSeconds(res.latency_ms?.total ?? 0)}</span>
              {cost && (
                <span className="num" title={`${res.usage?.total_tokens ?? 0} tokens`}>
                  {cost}
                </span>
              )}
              <button
                type="button"
                onClick={() => setWhyOpen((o) => !o)}
                aria-expanded={whyOpen}
                className="-ml-2 flex h-8 items-center gap-1.5 rounded-md px-2 font-medium text-ink hover:bg-surface/70"
              >
                Why? <IconChevron open={whyOpen} />
              </button>
            </div>
          </div>
          {escalated &&
            (ackAt ? (
              <p className="num shrink-0 pt-1.5 text-[13px] text-ink-2">
                Acknowledged by operator · {ackAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
              </p>
            ) : (
              <button
                type="button"
                onClick={() => setAckAt(new Date())}
                className="h-9 shrink-0 rounded-lg border border-field bg-surface px-3.5 text-[14px] font-medium text-ink hover:border-ink-2"
              >
                Acknowledge
              </button>
            ))}
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
    <div className="py-4 pr-6 pl-7">
      <h3 className="label mb-2">Gate checks</h3>
      <ul className="text-[14px]">
        {checks.map((c) => (
          <li key={c.code} className="grid min-h-8 grid-cols-[20px_minmax(0,1fr)_minmax(0,1.2fr)] items-center gap-2">
            {c.pass ? <IconCheck className="text-ink-3" /> : <IconCross className="text-tone-high" />}
            <span className={c.pass ? "text-ink-2" : "font-semibold text-ink"}>{c.label}</span>
            <span className={`num truncate text-right text-[13.5px] ${c.pass ? "text-ink-3" : "text-ink"}`} title={c.value}>
              {c.value}
            </span>
          </li>
        ))}
      </ul>
      {fallback && (
        <p className="num mt-1 text-[13px] text-amber">
          Thresholds missing from response · using defaults {t.confidence.toFixed(2)} / {t.similarity.toFixed(2)}
        </p>
      )}
    </div>
  );
}

import { useState } from "react";
import { fmtSeconds, gateChecks, langCode, normalizeStatus, reasonText, STATUS_TEXT, thresholdsOf } from "../lib/labels";
import type { TriageResponse } from "../types/triage";
import { IconCheck, IconChevron, IconCross } from "./Icons";

/**
 * The decision. Full width; its stripe and badge are the only full-strength status colour
 * on screen (B1). Reason sits right under the status (C3).
 */
export function EscalationBanner({ res }: { res: TriageResponse }) {
  const status = normalizeStatus(res.escalation?.status);
  const escalated = status === "escalate";
  const [whyOpen, setWhyOpen] = useState(escalated);
  const [ackAt, setAckAt] = useState<Date | null>(null);

  const reasons = res.escalation?.reasons ?? [];
  let reasonLine = reasons.length
    ? reasons.map((r) => reasonText(res, r.code, r.message)).join(" · ")
    : escalated
      ? "Escalated by the gate (no reason given)"
      : "No escalation rule triggered";
  if (!escalated && !res.draft) reasonLine += " · no draft returned"; // review #11
  const evidence = [res.guardrails?.prompt_injection?.evidence, res.guardrails?.unsupported_request?.evidence].filter(
    (e): e is string => !!e,
  );
  const unique = [...new Set(evidence)];
  const tone = escalated
    ? { tint: "bg-esc-tint", stripe: "bg-esc", text: "text-esc-text", badge: "bg-esc" }
    : { tint: "bg-ok-tint", stripe: "bg-ok", text: "text-ok-text", badge: "bg-ok" };

  return (
    <section aria-label="Escalation decision" className="relative overflow-hidden rounded-lg border border-line bg-surface">
      <span aria-hidden className={`absolute inset-y-0 left-0 w-1.5 ${tone.stripe}`} />
      <div className={`${tone.tint} pl-6`}>
        <div className="flex items-start gap-4 py-4 pr-5">
          <span aria-hidden className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full ${tone.badge} text-white`}>
            {escalated ? (
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                <path d="M8 3.5v5.5M8 12.2v.3" />
              </svg>
            ) : (
              <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3.5 8.5l3 3 6-6.5" />
              </svg>
            )}
          </span>
          <div className="min-w-0 flex-1">
            <p className={`text-[20px] leading-tight font-semibold tracking-[-0.01em] ${tone.text}`} role="status">
              {STATUS_TEXT[status]}
            </p>
            <p className="mt-1 text-[14.5px] font-medium text-ink">
              {reasonLine}
              {escalated && res.classification?.queue?.label && (
                <span className="font-normal text-ink-2"> · paging {res.classification.queue.label} on-call</span>
              )}
            </p>
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
        <div className="flex items-center gap-4 border-t border-line py-1.5 pr-3 text-[12.5px] text-ink-2">
          <span className="num">
            <span className="text-ink-3">lang</span> {langCode(res.input?.language_detected)}
          </span>
          <span className="num">
            <span className="text-ink-3">end-to-end</span> {fmtSeconds(res.latency_ms?.total ?? 0)}
          </span>
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
          <li key={c.code} className="grid h-7 grid-cols-[18px_minmax(0,1fr)_minmax(0,1.2fr)] items-center gap-2">
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

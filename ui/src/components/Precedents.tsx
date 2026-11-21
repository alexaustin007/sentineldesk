import { forwardRef, Fragment, useImperativeHandle, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { DUPLICATE_SIMILARITY, fmtScore, langCode, thresholdsOf, topSimilarity } from "../lib/labels";
import type { Precedent, TriageResponse } from "../types/triage";
import { IconChevron } from "./Icons";
import { PriorityLabel } from "./PriorityLabel";
import { Section } from "./Section";

export interface PrecedentsHandle {
  focus: (id: string) => void;
}

const MAX = 5; // C1

/**
 * Compact rows that expand to the full evidence (original ticket + full resolution).
 * One row open at a time; nothing starts open. A citation click opens + flashes its row (C5).
 */
export const Precedents = forwardRef<PrecedentsHandle, { res: TriageResponse; hoverId: string | null }>(function Precedents(
  { res, hoverId },
  ref,
) {
  const list = [...res.precedents].sort((a, b) => b.similarity - a.similarity).slice(0, MAX);
  const cited = new Set(res.draft?.citations ?? []);
  const [open, setOpen] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ id: string; n: number } | null>(null);
  const rows = useRef(new Map<string, HTMLLIElement>());

  useImperativeHandle(ref, () => ({
    focus(id) {
      setOpen(id);
      setFlash((f) => ({ id, n: (f?.n ?? 0) + 1 }));
      // Wait for the other row to collapse and this one to expand before scrolling.
      requestAnimationFrame(() => rows.current.get(id)?.scrollIntoView({ behavior: "smooth", block: "center" }));
    },
  }));

  const { t } = thresholdsOf(res);
  const top = topSimilarity(res);
  const allBelow = top !== null && top < t.similarity;

  return (
    <Section
      label={
        allBelow ? (
          <>
            Closest precedents · all below <span className="num">{fmtScore(t.similarity)}</span>, shown greyed
          </>
        ) : (
          <>Precedents · {list.length}</>
        )
      }
      meta={top !== null ? `top ${fmtScore(top)} sim · threshold ${fmtScore(t.similarity)}` : undefined}
    >
      {list.length === 0 ? (
        <p className="px-5 py-4 text-[14px] text-ink-2">No precedents retrieved.</p>
      ) : (
        <ul className="divide-y divide-line">
          {list.map((p) => {
            const isOpen = open === p.ticket_id;
            // Greyed with text tokens, not opacity, so contrast holds.
            const weak = p.similarity < t.similarity;
            const isCited = cited.has(p.ticket_id);
            const lit = hoverId === p.ticket_id;
            const strong = weak ? "text-ink-3" : "text-ink";
            const preview = p.answer ?? p.answer_snippet;
            return (
              <li
                key={flash?.id === p.ticket_id ? `${p.ticket_id}-${flash.n}` : p.ticket_id}
                id={`prec-${p.ticket_id}`}
                ref={(el) => {
                  if (el) rows.current.set(p.ticket_id, el);
                }}
                className={`scroll-mt-16 ${flash?.id === p.ticket_id ? "flash" : ""} ${lit ? "bg-accent-soft shadow-[inset_3px_0_0_var(--accent)]" : ""}`}
              >
                <button
                  type="button"
                  onClick={() => setOpen(isOpen ? null : p.ticket_id)}
                  aria-expanded={isOpen}
                  aria-controls={`prec-body-${p.ticket_id}`}
                  className="grid w-full grid-cols-[88px_minmax(0,1fr)_14px] items-start gap-x-4 px-5 py-2.5 text-left hover:bg-surface-2"
                >
                  <span className="pt-px">
                    <span className={`num block text-[13px] font-medium ${strong}`}>{p.ticket_id}</span>
                    <span className="num mt-0.5 flex items-center gap-1.5 text-[12px]">
                      <span className={weak ? "text-ink-3" : "font-medium text-ink-2"}>{fmtScore(p.similarity)}</span>
                      <span className="text-ink-3">sim</span>
                    </span>
                  </span>
                  <span className="min-w-0">
                    {/* Line 1: subject + lang · type · priority. Missing subject/language: cells drop out, no gaps. */}
                    <span className="flex min-w-0 items-baseline gap-3">
                      {p.subject && (
                        <span className={`min-w-0 truncate text-[14px] font-medium ${strong}`} title={p.subject}>
                          {p.subject}
                        </span>
                      )}
                      <Meta p={p} className={`shrink-0 text-[12.5px] ${p.subject ? "text-ink-3" : weak ? "text-ink-3" : "text-ink-2"}`} />
                    </span>
                    {/* Line 2: one-line resolution preview + tags. */}
                    <span className="mt-0.5 flex min-w-0 items-center gap-2">
                      <span className={`min-w-0 truncate text-[13px] ${weak ? "text-ink-3" : "text-ink-2"}`}>{preview}</span>
                      <span className="ml-auto flex shrink-0 items-center gap-2">
                        {isCited && (
                          <span className="num rounded-[3px] bg-accent-soft px-1.5 py-px text-[11px] font-medium text-accent">cited</span>
                        )}
                        {p.similarity >= DUPLICATE_SIMILARITY && (
                          <span className="rounded-[3px] border border-field px-1.5 py-px text-[11px] font-medium whitespace-nowrap text-ink-2">
                            Likely duplicate
                          </span>
                        )}
                      </span>
                    </span>
                  </span>
                  <IconChevron open={isOpen} className="mt-1 text-ink-3" />
                </button>
                {isOpen && <Evidence p={p} weak={weak} />}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
});

/** Expanded body: original ticket (clipped, Show more), full resolution (most room), label row. Scrolls inside. */
function Evidence({ p, weak }: { p: Precedent; weak: boolean }) {
  const [more, setMore] = useState(false);
  const [clipped, setClipped] = useState(false);
  const bodyRef = useRef<HTMLParagraphElement>(null);
  useLayoutEffect(() => {
    const el = bodyRef.current;
    if (el && !more) setClipped(el.scrollHeight > el.clientHeight + 1);
  }, [p.body, more]);

  const labels: ReactNode[] = [
    <span key="t">{p.type}</span>,
    <span key="q">{p.queue}</span>,
    <PriorityLabel key="p" label={p.priority} />,
  ];
  if (p.language) labels.push(<span key="l" className="num">{langCode(p.language)}</span>);
  labels.push(<span key="s" className="num">{fmtScore(p.similarity)} sim</span>);

  return (
    <div id={`prec-body-${p.ticket_id}`} className="max-h-[440px] overflow-y-auto overscroll-contain px-5 pb-4">
      <div className="ml-[104px] flex flex-col gap-4 border-l-2 border-line-strong pl-4">
        {p.body && (
          <div>
            <h4 className="label mb-1">Original ticket</h4>
            {p.subject && <p className="text-[13.5px] font-medium text-ink">{p.subject}</p>}
            <p
              ref={bodyRef}
              className={`mt-0.5 text-[13.5px] leading-relaxed whitespace-pre-line text-ink-2 ${more ? "" : "line-clamp-6"}`}
            >
              {p.body}
            </p>
            {(clipped || more) && (
              <button
                type="button"
                onClick={() => setMore((m) => !m)}
                aria-expanded={more}
                className="mt-1 inline-flex h-8 items-center text-[12.5px] font-medium text-accent hover:underline"
              >
                {more ? "Show less" : "Show more"}
              </button>
            )}
          </div>
        )}
        <div>
          <h4 className="label mb-1">Resolution</h4>
          <p className={`text-[14.5px] leading-[1.7] whitespace-pre-line ${weak ? "text-ink-2" : "text-ink"}`}>{p.answer ?? p.answer_snippet}</p>
        </div>
        <p className="flex flex-wrap items-center gap-1.5 text-[12px] text-ink-3">
          {labels.map((l, i) => (
            <span key={i} className="rounded-[3px] border border-line-strong px-1.5 py-px">
              {l}
            </span>
          ))}
        </p>
      </div>
    </div>
  );
}

/** "EN · Request · medium"; language is skipped when missing. */
function Meta({ p, className }: { p: Precedent; className: string }) {
  const parts: ReactNode[] = [];
  if (p.language) parts.push(<span className="num">{langCode(p.language)}</span>);
  parts.push(<span>{p.type}</span>, <PriorityLabel label={p.priority} />);
  return (
    <span className={`flex items-center gap-1.5 ${className}`}>
      {parts.map((node, i) => (
        <Fragment key={i}>
          {i > 0 && <span aria-hidden>·</span>}
          {node}
        </Fragment>
      ))}
    </span>
  );
}

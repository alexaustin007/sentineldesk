import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { DUPLICATE_SIMILARITY, fmtScore, langCode, thresholdsOf, topSimilarity } from "../lib/labels";
import type { TriageResponse } from "../types/triage";
import { IconChevron } from "./Icons";
import { PriorityLabel } from "./PriorityLabel";
import { Section } from "./Section";

export interface PrecedentsHandle {
  focus: (id: string) => void;
}

const MAX = 5; // C1

/** Compact rows. Top + cited start expanded. Linked to citation chips (C5). */
export const Precedents = forwardRef<PrecedentsHandle, { res: TriageResponse; hoverId: string | null }>(function Precedents(
  { res, hoverId },
  ref,
) {
  const list = [...res.precedents].sort((a, b) => b.similarity - a.similarity).slice(0, MAX);
  const cited = new Set(res.draft?.citations ?? []);
  const [open, setOpen] = useState<Set<string>>(
    () => new Set([...(list[0] ? [list[0].ticket_id] : []), ...list.filter((p) => cited.has(p.ticket_id)).map((p) => p.ticket_id)]),
  );
  const [flash, setFlash] = useState<{ id: string; n: number } | null>(null);
  const rows = useRef(new Map<string, HTMLLIElement>());

  useImperativeHandle(ref, () => ({
    focus(id) {
      setOpen((s) => new Set(s).add(id));
      setFlash((f) => ({ id, n: (f?.n ?? 0) + 1 }));
      rows.current.get(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
    },
  }));

  const { t } = thresholdsOf(res);
  const top = topSimilarity(res);
  const allBelow = top !== null && top < t.similarity;
  const toggle = (id: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

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
            const isOpen = open.has(p.ticket_id);
            // Greyed with text tokens, not opacity, so contrast holds (review #5).
            const weak = p.similarity < t.similarity;
            const isCited = cited.has(p.ticket_id);
            const lit = hoverId === p.ticket_id;
            const strong = weak ? "text-ink-3" : "text-ink";
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
                  onClick={() => toggle(p.ticket_id)}
                  aria-expanded={isOpen}
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
                    <span className="flex min-w-0 items-center gap-2">
                      <span className={`truncate text-[14px] font-medium ${strong}`} title={p.subject}>
                        {p.subject}
                      </span>
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
                    <span className="mt-0.5 flex min-w-0 items-center gap-1.5 truncate text-[12.5px] text-ink-3">
                      <span className="num">{langCode(p.language)}</span>
                      <span aria-hidden>·</span>
                      <span>{p.type}</span>
                      <span aria-hidden>·</span>
                      <PriorityLabel label={p.priority} />
                      <span aria-hidden>·</span>
                      <span className="truncate" title={p.queue}>
                        {p.queue}
                      </span>
                    </span>
                  </span>
                  <IconChevron open={isOpen} className="mt-1 text-ink-3" />
                </button>
                {isOpen && (
                  <div className="grid grid-cols-[88px_minmax(0,1fr)_14px] gap-x-4 px-5 pb-3.5">
                    <span />
                    <blockquote className={`border-l-2 border-line-strong pl-3 text-[13.5px] leading-relaxed ${weak ? "text-ink-3" : "text-ink-2"}`}>
                      “{p.answer_snippet}”
                    </blockquote>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
});

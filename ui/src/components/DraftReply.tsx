import { useState, type ReactNode } from "react";
import { fmtScore, langCode, normalizeStatus } from "../lib/labels";
import type { Precedent, TriageResponse } from "../types/triage";
import { IconCopy } from "./Icons";
import { Section } from "./Section";
import { toast } from "./Toast";

const CITE = /\[(TKT-\d{5})\]/g;

export function DraftReply({
  res,
  onCite,
  onHover,
}: {
  res: TriageResponse;
  onCite: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const status = normalizeStatus(res.escalation?.status);
  const escalated = status === "escalate";
  const internal = status !== "auto_draft"; // human_review / escalate drafts are internal notes
  const draft = res.draft;
  const byId = new Map(res.precedents.map((p) => [p.ticket_id, p]));
  const removed = res.guardrails?.removed_claims ?? [];

  if (!draft) {
    const gap = res.escalation?.reasons?.some((r) => r.code === "LOW_SIMILARITY");
    return (
      <Section label="Draft" meta="not generated">
        <p className="px-5 py-4 text-[14.5px] text-ink-2">
          {escalated
            ? "No draft: paged on-call before drafting"
            : gap
              ? "No draft: there is no past resolution to ground a reply in."
              : status === "human_review"
                ? "No draft: held for human review."
                : "No draft: the generator returned none."}
        </p>
        <RemovedClaims claims={removed} />
      </Section>
    );
  }

  const header = escalated ? "holding reply for engineer review" : status === "human_review" ? "for human review" : null;
  const copy = async () => {
    const text = internal ? `[Internal note · ${header}]\n\n${draft.text}` : draft.text;
    try {
      await navigator.clipboard.writeText(text);
      toast(internal ? "Copied as internal note" : "Draft copied");
    } catch {
      toast("Copy failed: clipboard not available");
    }
  };

  const cited = draft.citations ?? [];
  const found = cited.filter((c) => byId.has(c)).length;

  return (
    <Section
      label={
        <>
          Draft{header && <span> · {header}</span>} · {langCode(draft.language)}
        </>
      }
      meta={`${cited.length} citation${cited.length === 1 ? "" : "s"}`}
    >
      <div className="px-5 pt-4 pb-4">
        <p className="max-w-[86ch] text-[15px] leading-[1.75] text-ink">{renderWithCitations(draft.text, byId, onCite, onHover)}</p>
      </div>
      <RemovedClaims claims={removed} />
      <div className="flex items-center gap-3 border-t border-line px-5 py-2.5">
        <p className={`text-[12.5px] ${res.guardrails?.citations_valid === false ? "font-medium text-amber" : "text-ink-3"}`}>
          {res.guardrails?.citations_valid === false
            ? "Some citations do not match a retrieved precedent."
            : `Grounded in ${found} of ${res.precedents.length} precedent${res.precedents.length === 1 ? "" : "s"}`}
        </p>
        <button
          type="button"
          onClick={copy}
          className="ml-auto flex h-8 items-center gap-2 rounded-md border border-field bg-surface px-3 text-[13px] font-medium text-ink hover:border-ink-2"
        >
          <IconCopy />
          {internal ? "Copy as internal note" : "Copy draft"}
        </button>
      </div>
    </Section>
  );
}

/** Sentences the verifier deleted (unsupported promises): visible proof against hallucination. */
function RemovedClaims({ claims }: { claims: string[] }) {
  if (!claims.length) return null;
  return (
    <div className="border-t border-line px-5 py-3">
      <p className="text-[12.5px] font-medium text-ink-2">Removed by verifier (unsupported):</p>
      <ul className="mt-1 space-y-1">
        {claims.map((c, i) => (
          <li key={i} className="text-[13.5px] text-ink-3 line-through decoration-ink-3/70">
            “{c}”
          </li>
        ))}
      </ul>
    </div>
  );
}

function renderWithCitations(
  text: string,
  byId: Map<string, Precedent>,
  onCite: (id: string) => void,
  onHover: (id: string | null) => void,
) {
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE)) {
    const i = m.index ?? 0;
    if (i > last) parts.push(text.slice(last, i));
    parts.push(<CitationChip key={i} id={m[1]} p={byId.get(m[1])} onCite={onCite} onHover={onHover} />);
    last = i + m[0].length;
  }
  parts.push(text.slice(last));
  return parts;
}

/** `[TKT-xxxxx]` stays visible as a chip. Hover previews, click scrolls to + highlights the precedent (C5). */
function CitationChip({
  id,
  p,
  onCite,
  onHover,
}: {
  id: string;
  p: Precedent | undefined;
  onCite: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const show = () => {
    setOpen(true);
    onHover(id);
  };
  const hide = () => {
    setOpen(false);
    onHover(null);
  };
  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => p && onCite(id)}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        aria-describedby={open ? `pop-${id}` : undefined}
        className={`num relative mx-0.5 rounded-[3px] border px-1 py-px align-baseline text-[12.5px] leading-none transition-colors after:absolute after:-inset-x-1 after:-inset-y-2 after:content-[''] ${
          p
            ? "border-accent/40 bg-accent-soft text-accent hover:border-accent"
            : "cursor-not-allowed border-dashed border-amber-line text-amber"
        }`}
      >
        [{id}]
      </button>
      {open && (
        <span
          id={`pop-${id}`}
          role="tooltip"
          className="absolute top-full left-0 z-30 mt-2 block w-80 rounded-md border border-line-strong bg-surface p-3 text-left text-[13px] leading-snug shadow-lg"
        >
          {p ? (
            <>
              <span className="num flex justify-between text-[12px] text-ink-3">
                <span>{p.ticket_id}</span>
                <span>
                  {fmtScore(p.similarity)} sim{p.language ? ` · ${langCode(p.language)}` : ""}
                </span>
              </span>
              {p.subject && <span className="mt-1 block font-medium text-ink">{p.subject}</span>}
              <span className="mt-1 line-clamp-2 block text-ink-2">{p.answer_snippet}</span>
              <span className="mt-2 block text-[12px] text-ink-3">Click to jump to precedent</span>
            </>
          ) : (
            <span className="text-amber">{id} is not in the retrieved precedents.</span>
          )}
        </span>
      )}
    </span>
  );
}

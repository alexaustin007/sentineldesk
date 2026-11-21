import { useState, type ReactNode } from "react";
import { findCitations } from "../lib/citations";
import { fmtScore, langCode, normalizeStatus } from "../lib/labels";
import type { Precedent, TriageResponse } from "../types/triage";
import { IconCopy } from "./Icons";
import { Section } from "./Section";
import { toast } from "./Toast";


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

  // The draft is the main output: slightly stronger card, larger text (UI_WORKFLOW §5).
  const MAIN = "border-line-strong shadow-[0_1px_3px_rgb(0_0_0/0.06)]";

  if (!draft) {
    // The reason decides the line (PR #5: escalation takes priority; screening blocks return early).
    const codes = new Set((res.escalation?.reasons ?? []).map((r) => r.code));
    const blocked = codes.has("PROMPT_INJECTION") || codes.has("UNSUPPORTED_LANGUAGE") || res.input?.language_supported === false;
    const line = escalated
      ? "Flagged for on-call review before drafting a reply."
      : blocked
        ? "No draft: blocked by guardrails before drafting"
        : codes.has("LOW_SIMILARITY")
          ? "No draft: no close precedent to ground a reply"
          : status === "human_review"
            ? "No draft: held for human review"
            : "No draft: the generator returned none";
    return (
      <Section label="Draft reply" meta="not generated">
        <p className="text-[16px] text-ink-2">{line}</p>
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
      className={MAIN}
      label={header ? `Draft reply · ${header}` : "Draft reply"}
      meta={
        <>
          <span className="mono">{langCode(draft.language)}</span> · {cited.length} citation{cited.length === 1 ? "" : "s"}
        </>
      }
    >
      <p className="max-w-[80ch] text-[16px] leading-[1.6] text-ink">{renderWithCitations(draft.text, byId, onCite, onHover)}</p>
      <RemovedClaims claims={removed} />
      <div className="mt-5 flex items-center gap-4">
        <p className={`text-[14px] ${res.guardrails?.citations_valid === false ? "font-medium text-amber" : "text-ink-3"}`}>
          {res.guardrails?.citations_valid === false
            ? "Some citations do not match a retrieved precedent."
            : `Grounded in ${found} of ${res.precedents.length} precedent${res.precedents.length === 1 ? "" : "s"}`}
        </p>
        <button
          type="button"
          onClick={copy}
          className="ml-auto flex h-10 items-center gap-2 rounded-lg border border-field bg-surface px-4 text-[14.5px] font-medium text-ink hover:border-ink-2"
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
    <div className="mt-4 rounded-lg bg-surface-2 px-4 py-3">
      <p className="text-[14px] font-medium text-ink-2">Removed by verifier (unsupported)</p>
      <ul className="mt-1 space-y-1">
        {claims.map((c, i) => (
          <li key={i} className="text-[14.5px] text-ink-3 line-through decoration-ink-3/70">
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
  for (const c of findCitations(text)) {
    if (c.index > last) parts.push(text.slice(last, c.index));
    parts.push(<CitationChip key={c.index} id={c.id} p={byId.get(c.id)} onCite={onCite} onHover={onHover} />);
    last = c.index + c.length;
  }
  parts.push(text.slice(last));
  return parts;
}

/** `[TKT-xxxxx]` (or `[TKT-V5-xxxxx]`) stays visible as a chip. Hover previews, click scrolls to + highlights the precedent (C5). */
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
        className={`mono relative mx-0.5 rounded-[4px] border px-1 py-px align-baseline text-[13.5px] leading-none transition-colors after:absolute after:-inset-x-1 after:-inset-y-2 after:content-[''] ${
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
          className="absolute top-full left-0 z-30 mt-2 block w-80 rounded-lg border border-line-strong bg-surface p-3.5 text-left text-[14px] leading-snug shadow-lg"
        >
          {p ? (
            <>
              <span className="flex justify-between text-[13px] text-ink-3">
                <span className="mono">{p.ticket_id}</span>
                <span className="num">
                  {fmtScore(p.similarity)} sim{p.language ? ` · ${langCode(p.language)}` : ""}
                </span>
              </span>
              {p.subject && <span className="mt-1 block font-medium text-ink">{p.subject}</span>}
              <span className="mt-1 line-clamp-2 block text-ink-2">{p.answer_snippet}</span>
              <span className="mt-2 block text-[13px] text-ink-3">Click to jump to precedent</span>
            </>
          ) : (
            <span className="text-amber">{id} is not in the retrieved precedents.</span>
          )}
        </span>
      )}
    </span>
  );
}

import { useRef, type ReactNode } from "react";
import { SAMPLES, type Sample } from "../mocks";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
export const SHORTCUT = isMac ? "⌘↵" : "Ctrl+↵";

/** Splits `text` into nodes with every case-insensitive occurrence of `needles` wrapped in <mark>. */
function highlight(text: string, needles: string[]): ReactNode[] {
  const ranges: [number, number][] = [];
  const lower = text.toLowerCase();
  for (const n of needles) {
    if (!n) continue;
    let i = lower.indexOf(n.toLowerCase());
    while (i !== -1) {
      ranges.push([i, i + n.length]);
      i = lower.indexOf(n.toLowerCase(), i + n.length);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  const out: ReactNode[] = [];
  let pos = 0;
  merged.forEach(([a, b], k) => {
    if (a > pos) out.push(text.slice(pos, a));
    out.push(
      <mark key={k} className="rounded-[2px] bg-mark text-transparent">
        {text.slice(a, b)}
      </mark>,
    );
    pos = b;
  });
  out.push(text.slice(pos) + "\n");
  return out;
}

const FIELD = "w-full rounded-lg border border-field px-3.5 py-2.5 text-[15px] leading-[1.5]";

export function TicketInput({
  subject,
  body,
  onSubject,
  onBody,
  onSample,
  onSubmit,
  busy,
  bodyError,
  evidence,
  readOnly = false,
  variant = "pane",
  onNew,
}: {
  subject: string;
  body: string;
  onSubject: (v: string) => void;
  onBody: (v: string) => void;
  onSample: (s: Sample) => void;
  onSubmit: () => void;
  busy: boolean;
  bodyError: boolean;
  /** Guardrail evidence strings to highlight inside the body (wireframe D). */
  evidence: string[];
  readOnly?: boolean;
  /** "entry": the standalone first screen; "pane": compact left pane next to results. */
  variant?: "entry" | "pane";
  /** Shown in the pane variant: back to the entry-only view. */
  onNew?: () => void;
}) {
  const backdrop = useRef<HTMLDivElement>(null);
  const chipsOff = busy || readOnly;

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="flex min-h-8 items-center justify-between">
        <h2 className={variant === "entry" ? "text-[20px] font-semibold text-ink" : "heading"}>
          {variant === "entry" ? "Triage a ticket" : "Ticket"}
        </h2>
        {onNew && (
          <button
            type="button"
            onClick={onNew}
            className="flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-[14.5px] font-medium text-accent hover:bg-accent-soft"
          >
            <span aria-hidden className="text-[15px] leading-none">+</span> New ticket
          </button>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="subject" className="text-[14px] font-medium text-ink-2">
          Subject <span className="font-normal text-ink-3">optional</span>
        </label>
        <input
          id="subject"
          value={subject}
          readOnly={readOnly}
          onChange={(e) => onSubject(e.target.value)}
          className={`${FIELD} h-11 bg-surface`}
          autoComplete="off"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="body" className="text-[14px] font-medium text-ink-2">
          Body
        </label>
        <div className="relative rounded-md bg-surface">
          <div
            ref={backdrop}
            aria-hidden
            className={`${FIELD} pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words border-transparent text-transparent`}
          >
            {highlight(body, evidence)}
          </div>
          <textarea
            id="body"
            value={body}
            readOnly={readOnly}
            onChange={(e) => onBody(e.target.value)}
            onScroll={(e) => {
              if (backdrop.current) backdrop.current.scrollTop = e.currentTarget.scrollTop;
            }}
            rows={variant === "entry" ? 10 : 7}
            autoFocus={variant === "entry" && !readOnly}
            placeholder="Paste the customer's message"
            aria-invalid={bodyError}
            aria-describedby={bodyError ? "body-error" : undefined}
            className={`${FIELD} relative block min-h-36 resize-y bg-transparent placeholder:text-ink-3 ${bodyError ? "!border-amber" : ""}`}
          />
        </div>
        {bodyError && (
          <p id="body-error" className="text-[14px] font-medium text-amber">
            Body required
          </p>
        )}
        {evidence.length > 0 && (
          <p className="flex items-center gap-1.5 text-[13px] text-ink-3">
            <span className="inline-block h-2.5 w-4 rounded-[2px] bg-mark" /> guardrail evidence
          </p>
        )}
      </div>

      <button
        id="triage-btn"
        type="submit"
        aria-disabled={busy}
        className="flex h-12 w-full items-center justify-center gap-3 rounded-lg bg-accent-fill px-4 text-[15.5px] font-semibold text-accent-fill-ink transition-opacity hover:opacity-92 aria-disabled:cursor-progress aria-disabled:opacity-70"
      >
        {busy ? "Triaging…" : "Triage ticket"}
        <kbd className="rounded border border-current/35 px-1.5 py-px text-[12px] font-normal">{SHORTCUT}</kbd>
      </button>

      {/* Quiet example links (judges paste their own tickets). Fill only; never submit, no active state. */}
      <p className="-mt-1 flex flex-wrap items-center gap-x-1 text-[14px] text-ink-3">
        <span className="mr-1">Try an example:</span>
        {SAMPLES.map((s, i) => (
          <span key={s.id} className="inline-flex items-center">
            <button
              type="button"
              aria-disabled={chipsOff}
              onClick={() => !chipsOff && onSample(s)}
              className="inline-flex h-8 items-center rounded px-0.5 text-ink-2 underline decoration-line-strong underline-offset-[3px] hover:text-accent hover:decoration-accent aria-disabled:cursor-default aria-disabled:hover:text-ink-2 aria-disabled:hover:decoration-line-strong"
            >
              {s.label}
            </button>
            {i < SAMPLES.length - 1 && (
              <span aria-hidden className="ml-1">
                ·
              </span>
            )}
          </span>
        ))}
      </p>
    </form>
  );
}

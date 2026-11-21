import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";

/**
 * The app's own small tooltip (no library, F3), as a hook so any element can be the trigger
 * (a <span>, a table row, a header cell).
 * - Opens on hover and on keyboard focus (spread `props`, which include tabIndex=0); Escape, blur or
 *   a click elsewhere closes it. A tap toggles it on touch (hover/focus are ignored for touch pointers).
 * - The trigger gets aria-describedby → role="tooltip" while open.
 * - Rendered through a portal with fixed positioning: below the trigger, flipped above when there's no
 *   room, clamped to the viewport. It never covers its own trigger and is never clipped by a card or a
 *   scrolling table, and ancestor transforms can't misplace it.
 * - 360 px wide (420 px with `wide`, for tooltips that carry a table); 13/20 text.
 */
export function useTip(content: ReactNode, { wide = false }: { wide?: boolean } = {}) {
  const id = useId();
  const anchor = useRef<HTMLElement | null>(null);
  const tip = useRef<HTMLSpanElement>(null);
  const touch = useRef(false);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  // Bumped on scroll/resize so the tooltip follows its anchor. (Closing on scroll would kill it
  // for keyboard users: focusing an off-screen trigger scrolls it into view.)
  const [tick, setTick] = useState(0);

  useLayoutEffect(() => {
    if (!open) return setPos(null);
    const a = anchor.current?.getBoundingClientRect();
    const t = tip.current?.getBoundingClientRect();
    if (!a || !t) return;
    const m = 12;
    let top = a.bottom + 8;
    if (top + t.height > innerHeight - m) top = a.top - 8 - t.height > m ? a.top - 8 - t.height : Math.max(m, innerHeight - m - t.height);
    const left = Math.max(m, Math.min(a.left + a.width / 2 - t.width / 2, innerWidth - m - t.width));
    setPos({ top, left });
  }, [open, tick]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const follow = () => setTick((n) => n + 1);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    const onDown = (e: PointerEvent) => !anchor.current?.contains(e.target as Node) && close();
    window.addEventListener("scroll", follow, true);
    window.addEventListener("resize", follow);
    window.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("scroll", follow, true);
      window.removeEventListener("resize", follow);
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  const props = {
    // Typed loosely so the same props fit a span, a tr or a th.
    ref: anchor as unknown as RefObject<never>,
    tabIndex: 0,
    "aria-describedby": open ? id : undefined,
    onPointerDown: (e: { pointerType: string }) => void (touch.current = e.pointerType === "touch"),
    onMouseEnter: () => !touch.current && setOpen(true),
    onMouseLeave: () => !touch.current && setOpen(false),
    onFocus: () => !touch.current && setOpen(true),
    onBlur: () => setOpen(false),
    onClick: () => touch.current && setOpen((o) => !o),
  };

  const node = open
    ? createPortal(
        <span
          ref={tip}
          id={id}
          role="tooltip"
          style={pos ?? { top: -9999, left: -9999 }}
          className={`pointer-events-none fixed z-50 block max-w-[calc(100vw-24px)] rounded-lg border border-line-strong bg-surface px-4 py-3.5 text-left text-[13px] leading-5 font-normal text-ink shadow-lg ${wide ? "w-[420px]" : "w-[360px]"}`}
        >
          {content}
        </span>,
        document.body,
      )
    : null;

  return { props, node };
}

/** A tooltip trigger around inline content. Content must be phrasing content (spans). */
export function Tip({
  content,
  children,
  className = "",
  style,
  block = false,
  wide = false,
}: {
  content: ReactNode;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  block?: boolean;
  wide?: boolean;
}) {
  const { props, node } = useTip(content, { wide });
  return (
    <span {...props} className={`${block ? "block" : "inline-block"} cursor-help ${className}`} style={style}>
      {children}
      {node}
    </span>
  );
}

/** Standard tooltip body: bold title line, then lines of detail. */
export function TipBody({ title, children }: { title?: ReactNode; children?: ReactNode }) {
  return (
    <span className="block">
      {title && <span className="block font-semibold text-ink">{title}</span>}
      {children && <span className={`${title ? "mt-1.5 " : ""}block space-y-1.5`}>{children}</span>}
    </span>
  );
}

export function TipLine({ children }: { children: ReactNode }) {
  return <span className="block">{children}</span>;
}

/** 13/20 text + 3 px above and below + the 1 px rule ≈ 26 px rows. */
const ROW_PAD: CSSProperties = { paddingTop: 3, paddingBottom: 3 };

/** "Calibration error (ECE) 0.03": muted key, value after it. */
export function TipKV({ k, children }: { k: ReactNode; children: ReactNode }) {
  return (
    <span className="block">
      <span className="text-ink-2">{k}</span> {children}
    </span>
  );
}

/**
 * A small text table inside a tooltip (display: table on spans, so the tooltip stays valid phrasing content).
 * First column left-aligned, the rest right-aligned in tabular numbers; headers weight 500 with a thin rule
 * under them; faint row separators. Style a cell by passing a styled span.
 */
export function TipTable({
  head,
  rows,
}: {
  head: string[];
  rows: { key: string; cells: ReactNode[]; strong?: boolean }[];
}) {
  const align = (c: number) => (c === 0 ? "text-left pr-3" : "num text-right pl-3");
  return (
    <span className="mt-0.5 table w-full border-collapse">
      <span className="table-row">
        {head.map((h, c) => (
          <span key={h} style={ROW_PAD} className={`table-cell border-b border-line-strong font-medium text-ink-2 ${align(c)}`}>
            {h}
          </span>
        ))}
      </span>
      {rows.map((r, i) => (
        <span key={r.key} className="table-row">
          {r.cells.map((v, c) => (
            <span
              key={c}
              style={ROW_PAD}
              className={`table-cell border-b border-line/60 align-middle text-ink ${align(c)} ${r.strong ? "font-semibold" : ""} ${i === rows.length - 1 ? "border-b-0" : ""}`}
            >
              {v}
            </span>
          ))}
        </span>
      ))}
    </span>
  );
}

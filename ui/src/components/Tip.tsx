import { useEffect, useId, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

/**
 * The app's own small tooltip (no library, F3).
 * - Opens on hover and on keyboard focus; Escape, blur or scroll closes it.
 * - Touch: a tap toggles it (hover/focus are ignored for touch pointers).
 * - The trigger gets aria-describedby → role="tooltip" while open.
 * - Fixed positioning, flipped above when there's no room below and clamped to the viewport,
 *   so cards and scrolling tables never clip it.
 * Content must be phrasing content (spans), because the trigger is a <span>.
 */
export function Tip({
  content,
  children,
  className = "",
  style,
  block = false,
}: {
  content: ReactNode;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  block?: boolean;
}) {
  const id = useId();
  const anchor = useRef<HTMLSpanElement>(null);
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
    if (top + t.height > innerHeight - m && a.top - 8 - t.height > m) top = a.top - 8 - t.height;
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

  return (
    <span
      ref={anchor}
      tabIndex={0}
      aria-describedby={open ? id : undefined}
      className={`${block ? "block" : "inline-block"} cursor-help ${className}`}
      style={style}
      onPointerDown={(e) => (touch.current = e.pointerType === "touch")}
      onMouseEnter={() => !touch.current && setOpen(true)}
      onMouseLeave={() => !touch.current && setOpen(false)}
      onFocus={() => !touch.current && setOpen(true)}
      onBlur={() => setOpen(false)}
      onClick={() => touch.current && setOpen((o) => !o)}
    >
      {children}
      {open && (
        <span
          ref={tip}
          id={id}
          role="tooltip"
          style={pos ?? { top: -9999, left: -9999 }}
          className="pointer-events-none fixed z-50 block w-max max-w-[340px] rounded-lg border border-line-strong bg-surface px-3.5 py-3 text-left text-[13.5px] leading-snug font-normal text-ink-2 shadow-lg"
        >
          {content}
        </span>
      )}
    </span>
  );
}

/** Standard tooltip body: bold title line, then lines of detail. */
export function TipBody({ title, children }: { title: ReactNode; children?: ReactNode }) {
  return (
    <span className="block">
      <span className="block font-semibold text-ink">{title}</span>
      {children && <span className="mt-1 block space-y-1">{children}</span>}
    </span>
  );
}

export function TipLine({ children }: { children: ReactNode }) {
  return <span className="block">{children}</span>;
}

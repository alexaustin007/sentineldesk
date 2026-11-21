import type { ReactNode } from "react";

/**
 * One card per section (C2): generous padding, a sentence-case 17 px heading,
 * optional muted meta on the right. Whitespace, not dividers, separates the content.
 */
export function Section({
  label,
  meta,
  children,
  className = "",
  id,
  flush = false,
}: {
  label: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
  /** Content handles its own horizontal padding (lists, tables). */
  flush?: boolean;
}) {
  return (
    <section id={id} className={`rounded-xl border border-line bg-surface py-5 ${className}`}>
      <header className="flex min-h-8 items-center justify-between gap-4 px-6">
        <h2 className="heading">{label}</h2>
        {meta && <div className="num text-[13px] text-ink-3">{meta}</div>}
      </header>
      <div className={flush ? "mt-2" : "mt-3 px-6"}>{children}</div>
    </section>
  );
}

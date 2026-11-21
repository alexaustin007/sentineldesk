import type { ReactNode } from "react";

/** One bounded region with a small-caps label (C2). `meta` is a short right-aligned fact from the response. */
export function Section({
  label,
  meta,
  children,
  className = "",
  id,
}: {
  label: ReactNode;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`rounded-lg border border-line bg-surface ${className}`}>
      <header className="flex min-h-10 items-center justify-between gap-3 border-b border-line px-5 py-2">
        <h2 className="label">{label}</h2>
        {meta && <div className="num text-[12px] text-ink-3">{meta}</div>}
      </header>
      {children}
    </section>
  );
}

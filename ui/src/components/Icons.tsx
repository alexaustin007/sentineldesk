// Minimal inline icons (no icon library, F3). 16px, currentColor.
type P = { className?: string };
const base = "inline-block shrink-0";

export const IconCopy = ({ className = "" }: P) => (
  <svg viewBox="0 0 16 16" width="14" height="14" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
    <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
    <path d="M10.5 3.5v-.5A1.5 1.5 0 0 0 9 1.5H4A1.5 1.5 0 0 0 2.5 3v5A1.5 1.5 0 0 0 4 9.5h.5" />
  </svg>
);
export const IconCheck = ({ className = "" }: P) => (
  <svg viewBox="0 0 16 16" width="14" height="14" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
    <path d="M3 8.5l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
export const IconCross = ({ className = "" }: P) => (
  <svg viewBox="0 0 16 16" width="14" height="14" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
    <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
  </svg>
);
export const IconChevron = ({ className = "", open = false }: P & { open?: boolean }) => (
  <svg
    viewBox="0 0 16 16"
    width="12"
    height="12"
    className={`${base} transition-transform ${open ? "rotate-90" : ""} ${className}`}
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    aria-hidden
  >
    <path d="M6 3.5l4.5 4.5L6 12.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
export const IconSun = ({ className = "" }: P) => (
  <svg viewBox="0 0 16 16" width="15" height="15" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
    <circle cx="8" cy="8" r="3" />
    <path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1" strokeLinecap="round" />
  </svg>
);
export const IconMoon = ({ className = "" }: P) => (
  <svg viewBox="0 0 16 16" width="15" height="15" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
    <path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7z" strokeLinejoin="round" />
  </svg>
);
export const IconSpinner = ({ className = "" }: P) => (
  <svg viewBox="0 0 16 16" width="14" height="14" className={`${base} spin ${className}`} fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
    <path d="M8 2a6 6 0 1 1-6 6" strokeLinecap="round" />
  </svg>
);
export const IconDot = ({ className = "" }: P) => (
  <svg viewBox="0 0 16 16" width="14" height="14" className={`${base} ${className}`} fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
    <circle cx="8" cy="8" r="3.25" />
  </svg>
);

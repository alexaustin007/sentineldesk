import { priorityTone } from "../lib/labels";

const TONE = {
  high: "text-tone-high",
  medium: "text-tone-medium",
  low: "text-tone-low",
  neutral: "text-ink-3",
} as const;

/** Colours only high/medium/low (muted, never the banner red). Any other value is neutral grey text. */
export function PriorityLabel({ label, className = "" }: { label: string; className?: string }) {
  const tone = priorityTone(label);
  return <span className={`${TONE[tone]} ${className}`}>{label || "—"}</span>;
}

// Pure text helpers for the Metrics tooltips (no runtime imports, so node can test them).
import type { HeadMetrics } from "../types/metrics";

export interface Confusion {
  from: string;
  to: string;
  count: number;
}

/** The largest off-diagonal cell: actual class `from` most often predicted as `to`. Null if there are no errors. */
export function mostConfused(h: HeadMetrics): Confusion | null {
  let best: Confusion | null = null;
  h.confusion.forEach((row, i) =>
    row.forEach((count, j) => {
      if (i !== j && count > 0 && (!best || count > best.count)) best = { from: h.labels[i], to: h.labels[j], count };
    }),
  );
  return best;
}

import type { HeadMetrics } from "../types/metrics";
import { Tip } from "./Tip";

/** "Service Outages and Maintenance" → "SOM", "IT Support" → "ITS"; unique within the head. */
export function abbreviations(labels: string[]): string[] {
  const seen = new Map<string, number>();
  return labels.map((l) => {
    const words = l.split(/[\s/-]+/).filter((w) => w && !/^(and|of|the|&)$/i.test(w));
    let a = words.length === 1 ? words[0].slice(0, 4) : words.map((w) => (/^[A-Z]{2,}$/.test(w) ? w : w[0])).join("");
    a = a.length <= 4 && words.length === 1 ? a : a.toUpperCase();
    const n = seen.get(a) ?? 0;
    seen.set(a, n + 1);
    return n ? `${a}${n + 1}` : a;
  });
}

const fmt = (n: number) => n.toLocaleString("en-US");
const pct0 = (x: number) => `${Math.round(x * 100)}%`;

/**
 * Heatmap of counts: rows = actual class, columns = predicted. Shade = share of the actual class
 * (said once, in the cell tooltip); the diagonal gets only a subtle weight emphasis.
 * Long labels use short column codes, mapped beside each row name; support sits next to the row label.
 */
export function ConfusionMatrix({ head, bare = false }: { head: HeadMetrics; bare?: boolean }) {
  const { labels, confusion } = head;
  const short = abbreviations(labels);
  const useShort = labels.some((l) => l.length > 9);
  const n = labels.length;
  const support = confusion.map((row) => row.reduce((a, b) => a + b, 0));
  const shade = (s: number) => `color-mix(in srgb, var(--accent) ${Math.round(6 + s * 84)}%, var(--surface))`;
  return (
    <div className={`overflow-x-auto ${bare ? "" : "px-6 pt-1"}`}>
      <table className="w-full border-separate border-spacing-[3px] text-[13.5px]" aria-label="Confusion matrix: rows are the actual class, columns the predicted class">
        <thead>
          <tr>
            <th colSpan={2} />
            <th colSpan={n} scope="colgroup" className="pb-1 text-center text-[13px] font-medium text-ink-3">
              Predicted
            </th>
          </tr>
          <tr>
            <th colSpan={2} />
            {labels.map((l, j) => (
              <th key={l} scope="col" title={l} className="h-7 min-w-12 px-1 text-center align-bottom font-medium text-ink-2">
                {useShort ? short[j] : l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {confusion.map((row, i) => {
            const total = support[i] || 1;
            return (
              <tr key={labels[i]}>
                {i === 0 && (
                  <th rowSpan={n} scope="rowgroup" className="w-6 pr-1 align-middle">
                    <span className="block rotate-180 text-[13px] font-medium text-ink-3 [writing-mode:vertical-rl]">Actual</span>
                  </th>
                )}
                <th scope="row" className="max-w-[280px] pr-3 text-left font-normal whitespace-nowrap text-ink">
                  {useShort && <span className="mr-2 inline-block w-10 text-ink-3">{short[i]}</span>}
                  {labels[i]}
                  <span className="num ml-2 text-[12.5px] text-ink-3">{fmt(support[i])}</span>
                </th>
                {row.map((v, j) => {
                  const share = v / total;
                  return (
                    <td
                      key={j}
                      className={`h-10 rounded-[4px] p-0 text-center ${i === j ? "font-semibold" : ""}`}
                      style={{
                        background: v ? shade(share) : "var(--surface-2)",
                        color: share > 0.5 ? "var(--surface)" : v ? "var(--ink)" : "var(--ink-3)",
                      }}
                    >
                      <Tip
                        block
                        className="num h-10 rounded-[4px] leading-10"
                        content={
                          <>
                            <span className="block text-ink">
                              Actual {labels[i]} → predicted {labels[j]} · {fmt(v)} tickets · {pct0(share)} of actual {labels[i]}
                            </span>
                            <span className="mt-0.5 block text-[12.5px] text-ink-3">Shade = share of the actual class</span>
                          </>
                        }
                      >
                        {v}
                      </Tip>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

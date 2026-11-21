import { Section } from "../components/Section";

const HEADS = ["type", "queue", "priority"];

/** Placeholder until the eval script writes metrics.json (UI_WORKFLOW §4.2). */
export function MetricsPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3">
      <Section label="Holdout metrics" meta="metrics.json · not yet available">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-line text-left">
              <th className="label px-5 py-2.5 font-semibold">Head</th>
              <th className="label px-5 py-2.5 text-right font-semibold">Macro-F1</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {HEADS.map((h) => (
              <tr key={h}>
                <td className="px-5 py-2.5 text-ink">{h}</td>
                <td className="num px-5 py-2.5 text-right text-ink-3">—</td>
              </tr>
            ))}
            <tr>
              <td className="px-5 py-2.5 text-ink">High-Priority Incident Recall</td>
              <td className="num px-5 py-2.5 text-right text-ink-3">—</td>
            </tr>
          </tbody>
        </table>
      </Section>
      <Section label="Splits">
        <p className="px-5 py-3 text-[13px] text-ink-2">
          kb_train / test sizes appear here. Test answers are never indexed.
        </p>
      </Section>
    </div>
  );
}

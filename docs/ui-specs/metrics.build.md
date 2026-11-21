# Metrics tab: build notes

Built from scratch to [`metrics.md`](metrics.md) (v2), which replaces every earlier Metrics instruction. One centred report column (880 px) with three question-titled sections, exactly one table, and hover/focus tooltips with dotted-underline triggers. There are no icons, "More info", charts, bars or panels. Data comes from `contracts/metrics.example.json` with no schema change.

## `metrics.json` shape (for Ivy's eval script)

Example: [`contracts/metrics.example.json`](../../contracts/metrics.example.json). It's placeholder data, but self-consistent: per-class precision, recall and F1, macro-F1 and accuracy are all computed from the confusion matrices.

| Field | Type | Required | Used for |
|---|---|---|---|
| `sample` | bool | no | `true` only in the example: the subtitle starts with "Sample data ·" and an amber dot. The eval script should omit it or set it to `false` |
| `generated_at` | ISO 8601 (UTC) | no | "updated 21 Nov, 14:00 UTC" in the meta line |
| `model`, `dataset` | string | no | The meta line |
| `split` | `{ train, knowledge_base, holdout, leakage_check, leakage_detail }` | no | Holdout fact + its tooltip (all three sizes); Leakage check fact (the leading count in `leakage_check` becomes "0 overlaps") + its tooltip (`leakage_check` and `leakage_detail`) |
| `heads.{type,queue,priority}.macro_f1` | number 0–1 | **yes** | The Macro-F1 column |
| `heads.*.labels`, `per_class[]`, `confusion` | see below | **yes** | Row tooltip: per-class table (`label`, `f1`, `precision`, `recall`, `support`) and "Most often confused" from the largest off-diagonal `confusion` cell (square, rows = true label, cols = predicted) |
| `heads.*.accuracy` | number 0–1 | no | Accuracy column |
| `heads.*.macro_f1_by_language` | `{ en, de }` | no | English and German columns |
| `heads.*.calibration_error` | number | no | Calibration error column (ECE, lower is better) |
| `calibration_error` | number | no | Not shown on this page now; kept in the schema (no schema change) |
| `high_priority_incident_recall` | number 0–1 | **yes** | The hero number, shown as 91.3% |
| `high_priority_incident` | `{ caught, total, escalation_rate? }` | no | "409 of 448 escalated to on-call" and the hero tooltip |
| `escalation_tradeoff[]` | `{ target_recall, escalation_rate, precision?, tickets_escalated? }` | no | The trade-off sentence (90% row, else the middle row) and its tooltip table |
| `pipeline.latency_ms` | `{ p50, p95 }` | no | Median latency fact; p50/p95 in its tooltip |
| `pipeline.stage_latency_ms` | `{ stage key: ms }` | no | The stage table in the latency tooltip |
| `pipeline.avg_cost_usd`, `cost_breakdown_usd`, `cost_basis` | number / map / string | no | Cost per ticket fact and its tooltip |
| `pipeline.status_mix`, `pipeline.tickets` | shares / count | no | Outcome mix line and the counts in its tooltip (`tickets` falls back to the holdout size) |
| `drafts` | `{ citations_valid_rate, language_match_rate, removed_claims_rate }` or `null` | no | An extra "Draft quality" fact, only when present |

If a required field is missing or the wrong type, the tab shows "Metrics file is missing or invalid: <every bad field>" with a Retry link. Malformed optional parts are dropped.

## Where the file comes from

`ui/src/lib/metrics.ts` fetches `/metrics.json` with `cache: no-store`.
- **Served as JSON** (copied to `ui/public/metrics.json`, or served by the backend through the `/api` proxy): parsed, and labelled real data unless it carries `sample: true`.
- **Not served** (a 404, or the Vite dev server's HTML fallback): the bundled `contracts/metrics.example.json` is used and labelled "Sample data ·". So in dev, and until Ivy's eval writes the file, the tab always shows the sample.
- **Served but malformed:** the invalid-file state. The tab is never blank.

The runtime check is `ui/src/lib/validateMetrics.ts` (hand-written, F3, no runtime imports).

## Built to the spec

- **Page:** title 24/32, subtitle 14/20, then three sections, each preceded by a hairline rule, with the question as a 17/24 heading:
  1. *Does it catch urgent incidents?* The hero **91.3%** (44/48), "High-priority incident recall · 409 of 448 escalated to on-call", and the trade-off sentence.
  2. *How accurate is the triage?* One table with the columns Macro-F1 · Accuracy · English · German · Calibration error, one row each for Type, Queue and Priority.
  3. *Is the evaluation sound, and is it fast?* Four facts (Holdout, Leakage check, Median latency, Cost per ticket; a fifth, Draft quality, only with `drafts`), the Outcome mix line in status colours, and the meta line.
- **Triggers:** every hoverable number or phrase has a dotted underline and `cursor: help`: the hero, the trade-off sentence, the five column headers (one-line definitions), the three table rows (per-class table plus "Most often confused"), the four facts and the outcome mix. A whole table row is the trigger for its tooltip.
- **Tooltip** (`ui/src/components/Tip.tsx`, no library): now a hook (`useTip`) plus a `Tip` component. Tooltips render through a portal (so a `<tr>` can be a trigger), 360 px wide (420 px for tables), 13/20 text, 16 px padding. They open on hover and focus, toggle on tap, close on Escape, and sit below the trigger, flipping above when there's no room. Inner tables follow the main table's rules: right-aligned tabular numbers, header weight 500 with a thin rule, faint separators, F1 below 0.70 amber.
- **Hiding optional data:** an optional table column shows only when every head has the value, and a fact, row or line appears only when its fields exist. There are no empty cells and no "N/A".
- **Removed:** the old tile and "More info" layout, the lean-layout footer, and the two components (`MetricCharts.tsx`, `ConfusionMatrix.tsx`) deleted earlier. No Metrics-only helper is left unused (`metricsText.ts` feeds "Most often confused").

## Acceptance checklist (results, 1440 × 900)

- [x] **All three sections visible without scrolling at 900 px tall.** The last line of the page (the meta line) ends at y = 867 px. The document is 939 px tall only because of bottom padding.
- [x] **Exact metric names visible on the page.** "High-priority incident recall", "Macro-F1" (column header), "Type" / "Queue" / "Priority", "holdout" (subtitle and the Holdout fact) and "latency" (Median latency) are all in the page text.
- [x] **No all caps, "More info", ⓘ, charts, bars or panels.** In the browser: 0 elements with `text-transform: uppercase`, 0 `aria-expanded` controls, 0 SVGs on the page body, and no text matching "more info". No element on the tab uses a monospace font.
- [x] **Exactly one table.** `document.querySelectorAll("table").length` is 1. All 15 numeric cells are right-aligned in tabular numbers. Macro-F1 is weight 600. The amber values are 0.63 (Queue Macro-F1), 0.64 and 0.62 (Queue English and German) and 0.69 (Priority German); Priority Macro-F1 0.71 and everything else stay neutral.
- [x] **Every tooltip trigger opens on hover and on Tab focus.** All 15 triggers open on focus (hero, sentence, 5 column headers, 3 rows, 4 facts, outcome mix), and the Draft quality fact does too in `#metrics-drafts`. A real mouse hover was also done on the Queue row. In light and dark none covers its trigger or leaves the viewport. The tall Queue tooltip (about 400 px) flips above its row.
- [x] **Typography matches the table** (computed styles):

  | Element | Computed | Spec |
  |---|---|---|
  | Page title | 24px/32px, 600, Inter | 24/32, 600 |
  | Section question | 17px/24px, 600 | 17/24, 600 |
  | Hero number | 44px/48px, 600, tabular-nums | 44/48, 600 |
  | Table cell (Macro-F1) | 15px/24px, 600 | 15/24, 600 |
  | Table cell (other) | 15px/24px, 400 | 15/24, 400 |
  | Column header | 13px/18px, 500 | 13/18, 500 |
  | Meta label | 13px/18px, 400 | 13/18, 400 |
  | Subtitle | 14px/20px, 400 | 14/20 |
  | Fact value | 17px/24px, 500 | 17/24, 500 |

  Tooltip text is 13/20.
- [x] **Light and dark themes both readable; body and meta text at least 4.5:1.** Dark was measured in the browser: meta, subtitle and labels 6.94:1, and the status-coloured outcome words at least 11:1. Light follows from the same tokens (`ink-3` on the page background is 5.8:1, computed). Screenshots were checked in both themes.
- [x] **Missing-optional-field and invalid-file states render as specified**, on `/dev/states`:
  - `#metrics-invalid`: "Metrics file is missing or invalid: heads.queue.confusion (must be 10×10, …), high_priority_incident_recall" and a Retry link.
  - `#metrics-minimal`: only the Macro-F1 column and the hero; no facts, no outcome mix, no meta line, 0 empty cells.
  - `#metrics-loading`, `#metrics-sample`, `#metrics-real` (subtitle "Evaluated on 4,000 holdout tickets the model never saw", no sample notice) and `#metrics-drafts` (extra Draft quality fact, "97% citations valid").
- [x] **Typecheck, build and `node ui/src/lib/validate.test.ts` pass** (24 checks).

## Decisions and deviations

- **UTC time.** `generated_at` is UTC, so the meta line says "updated 21 Nov, 14:00 UTC" instead of dropping the zone (the spec sketch shows no suffix).
- **A column needs every head.** An optional table column is hidden unless Type, Queue and Priority all have it.
- **Leakage value.** "0 overlaps" is parsed from the leading count of `leakage_check`; if it can't be parsed, the fact shows "Checked".
- **"Most often confused" line** is 12.5 px, not 13: it must stay on one line, and at 13 px the queue example's names would be cut.
- **Subtitle.** The sample subtitle reads "Sample data ·  evaluated on …" with the amber dot, as specified.

## Known gaps

- Not checked below 1440 px. The table scrolls inside its own box under 520 px, and the facts go two per row below 900 px.
- The sample numbers are placeholders. Nothing writes `metrics.json` yet (see the spec's "Data source status": it needs a small `classification/evaluate.py`).

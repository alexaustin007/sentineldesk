# Metrics tab: build notes

Replaces the placeholder Metrics tab (UI_WORKFLOW §4.2). It reports the holdout numbers the hackathon spec requires (Macro-F1 per head and High-Priority Incident Recall) from a static `metrics.json`, so there's no live compute.

## `metrics.json` shape (for Ivy's eval script)

Example: [`contracts/metrics.example.json`](../../contracts/metrics.example.json). It's placeholder data, but self-consistent: per-class precision, recall and F1, macro-F1 and accuracy are all computed from the confusion matrices.

| Field | Type | Required | Notes |
|---|---|---|---|
| `sample` | bool | no | `true` only in the example. The UI then shows the "Sample data" notice. The eval script should omit it or set it to `false`. |
| `generated_at` | ISO 8601 string | no | Shown in the header and footer |
| `model` | string | no | e.g. `"TF-IDF + LinearSVC (calibrated)"` |
| `dataset` | string | no | e.g. `"dataset-tickets-multi-lang-4-20k.csv"` |
| `split` | `{ train, knowledge_base, holdout, leakage_check, leakage_detail }` | no | Row counts plus one sentence about the leakage check, shown in the footer. `leakage_detail` (how the check was done) appears in the footer tooltip |
| `heads.{type,queue,priority}.macro_f1` | number 0–1 | **yes** | Headline tiles |
| `heads.*.accuracy` | number 0–1 | no | Shown under each tile |
| `heads.*.labels` | string[] | **yes** | Order of the confusion rows and columns |
| `heads.*.per_class[]` | `{ label, precision, recall, f1, support }` | **yes** (`label`, `f1`, `support`) | Per-class table |
| `heads.*.confusion` | number[][] | **yes** | Square, `labels.length` × `labels.length`; **rows = true label, cols = predicted** |
| `high_priority_incident_recall` | number 0–1 | **yes** | The most prominent tile |
| `high_priority_incident` | `{ caught, total, escalation_rate? }` | no | The counts behind the recall (holdout tickets with priority = high **and** type = Incident; caught = escalated) and the share of all tickets escalated at this operating point. Shown in the recall tile's tooltip; `caught / total` should equal the recall |
| `escalation_tradeoff[]` | `{ target_recall, escalation_rate, precision?, tickets_escalated? }` | no | From CLASSIFICATION_PLAN.md §7.3, e.g. 0.80, 0.90 and 0.95. `precision` = share of escalated tickets that really are high-priority incidents; `tickets_escalated` = absolute holdout count. Keep `precision × tickets_escalated ≈ target_recall × high_priority_incident.total` (the test checks it). Shown in that row's panel |
| `pipeline.status_mix` | `{ auto_draft, human_review, escalate }` | no (nullable) | Fractions or counts; the UI normalizes them to shares |
| `pipeline.latency_ms` | `{ p50, p95 }` | no (nullable) | |
| `pipeline.stage_latency_ms` | `{ <PR #5 stage key>: ms }` | no | Median per stage over the tickets where it ran (latency panel) |
| `pipeline.avg_cost_usd` | number | no (nullable) | |
| `pipeline.cost_breakdown_usd` | `{ <stage key>: usd }` | no | Average per ticket by LLM stage; should sum to `avg_cost_usd` (cost panel) |
| `pipeline.cost_basis` | string | no | How the cost was estimated (cost tooltip) |
| `pipeline.tickets` | number | no | Tickets the pipeline stats were measured on; turns status-mix shares into counts in the segment tooltips |

If a required field is missing or the wrong type, the tab shows an error listing every bad path, with Retry. Malformed optional parts are dropped and their sections hidden.

## Where the file comes from

`ui/src/lib/metrics.ts` fetches `/metrics.json` with `cache: no-store`.
- **Served as JSON** (copied to `ui/public/metrics.json`, or served by the backend through the `/api` proxy setup): it's parsed. If it doesn't carry `sample: true`, it's labelled live data.
- **Not served** (a 404, or the Vite dev server's HTML fallback): the bundled `contracts/metrics.example.json` is used, with one calm line under the title: "● Sample data: real metrics not generated yet". To replace it, copy the eval output to `ui/public/metrics.json`.
- **Served but malformed:** a `BAD_METRICS` error state with the message and Retry. The tab is never left blank.

The runtime check is `ui/src/lib/validateMetrics.ts`. It's hand-written (F3) and has no runtime imports, so the Node test can import it.

## Layout: calm readings, each with its own "More info" panel

Readability rules as on the console: Inter with tabular numbers, a 15 px base, sentence case, 17 px headings, no all caps, whitespace instead of dividers, and contrast of at least 4.5:1. There are no captions under the numbers and no bottom "Model details" section: every bit of detail sits in the panel of the reading it explains.

**First view**
1. Title "Model metrics", with one muted line: the sample notice (when it applies) and the holdout size.
2. **Four tiles**, each just a title, a number and a quiet **ⓘ More info** button: "Urgent incidents caught 91%" (largest), "Ticket type 0.77", "Queue routing 0.63", "Priority 0.71".
3. **Escalation trade-off card:** one sentence ("To catch 90% of urgent incidents, 26% of tickets go to a human.") and three rows (catch rate, bar, share escalated), each with its own More info.
4. **Pipeline row:** status-mix mini bar with "52% auto-draft", "1.48 s typical" and "$0.0009 per ticket", each with More info.
5. **Footer** (small, muted): split sizes with More info, model, dataset and generated time.

**Panels**
- **How they open and close:**
  - The More info button is focusable, has `aria-expanded` / `aria-controls`, and flips to "Less info".
  - The panel opens directly under the row holding its reading. The reading stays highlighted (an accent border on tiles, an accent-soft background on rows), and a small pointer on the panel's top edge aims at it.
  - Only one panel is open at a time. Clicking again, the × button or Esc closes it, and Esc returns focus to the trigger.
- **What each panel holds** (definition first, then a hand-made SVG/CSS visual):
  - **Urgent incidents caught:** the definition; "409 of 448 caught, 39 missed" as a caught (green) / missed (red) bar; "27% of all tickets are escalated (1,080 of 4,000)"; and a tiny recall-vs-escalation chart of the 80/90/95% points with the current setting marked "now".
  - **Ticket type / Queue routing / Priority:** the macro-F1 definition with plain accuracy; F1-by-class bars with ticket counts (amber below 0.60); **that head's confusion matrix** (moved here; Type / Queue / Priority switch removed); and the precision/recall table.
  - **Trade-off row (e.g. 90%):** escalated count, precision and misses, plus a stacked bar of all 4,000 holdout tickets: urgent and escalated (green), escalated but not urgent (neutral), not escalated.
  - **Status mix:** a stacked bar of auto-draft / human review / escalate (status colours) with counts, plus what each status means.
  - **Latency:** p50/p95 definitions, a 0…p95 scale with both markers, and median-per-stage bars from `stage_latency_ms`.
  - **Cost:** average per ticket and per 1,000 tickets, `cost_basis`, and per-stage cost bars from `cost_breakdown_usd`.
  - **Split sizes:** a train + knowledge base / holdout bar and what each split is for, then the leakage check line and `leakage_detail`.
- **Hover tooltips** are light only: exact values on chart bars and segments (via `Tip`) and on confusion-matrix cells. Matrix headers use a native `title`. SVG chart points use `<title>`.
- **Colour** carries meaning only: caught/missed, the three statuses, and amber for weak F1. All other bars are neutral.

**States:** loading (four tile placeholders), error ("The metrics file is not in the expected shape", the message, `BAD_METRICS` and Retry), and ready.

## Files

- `contracts/metrics.example.json` (new; the only file added under `contracts/`)
- `ui/src/types/metrics.ts`
- `ui/src/lib/validateMetrics.ts`, `ui/src/lib/metrics.ts`
- `ui/src/components/ConfusionMatrix.tsx`
- `ui/src/components/Tip.tsx`: the app's own tooltip (hover, focus, tap; `aria-describedby`)
- `ui/src/components/MetricCharts.tsx`: hand-made `StackedBar`, `BarList`, `TradeoffChart` (SVG) and `ScaleMarkers`
- `ui/src/pages/MetricsPage.tsx` (rewritten)
- `ui/src/lib/validate.test.ts`: 6 metrics checks: the example passes; supports equal the confusion row sums; a non-square matrix and a missing recall are both listed; malformed optional parts are dropped; the hover fields are consistent (`caught / total` = recall, `tickets_escalated` = rate × holdout); malformed hover fields are dropped; panel fields agree (urgent caught = recall × total = precision × escalated, the cost breakdown sums to the average, malformed stage maps are dropped). The file has 19 checks in total.

## Verified

- `npm --prefix ui run typecheck`, `npm --prefix ui run build` and `node ui/src/lib/validate.test.ts` (19 checks) pass.
- At 1440 px:
  - All 11 More info buttons open the right panel with a pointer, one at a time. Esc closes and returns focus, and clicking again closes. No captions and no "Model details" section remain.
  - Light: the recall panel (`v10-recall-panel-light.png`) and the 90% trade-off panel (`v10-tradeoff-panel-light.png`).
  - Dark: the queue panel with F1 bars, a 10×10 matrix that doesn't overflow, and the precision/recall table (`v10-queue-panel-dark.png`).
- No review loop, per the team.

## Known gaps

- Not checked below 1440 px. The tiles go 2×2 below `lg`, and panels then open under the whole tile grid with the pointer still aimed at the tile.
- Each confusion-matrix cell is a tab stop (100 for queue). A roving-tabindex grid would be nicer.
- The sample numbers are placeholders until Ivy's eval writes the real `metrics.json`.

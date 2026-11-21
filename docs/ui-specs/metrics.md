# Metrics tab: redesign spec (v2)

Replaces every earlier Metrics instruction (tiles, "More info" panels, charts, hover-only tables, labelled-facts footer). Data stays in `contracts/metrics.example.json` with no schema change.

## Purpose
Answer the three questions a judge asks about the model in about 10 seconds, with the exact numbers one hover away.

1. **Does it catch urgent incidents?** High-priority incident recall, required by the spec.
2. **How accurate is the triage?** Macro-F1 for type, queue and priority, required by the spec.
3. **Can we trust the evaluation, and is it fast and cheap?** Holdout size, leakage check, latency (implied by the spec), cost.

## Data source status (checked against main after team PRs #7 and #8)
- Nothing writes `metrics.json` yet. Ivy's `classification/train.py` prints Macro-F1 to the terminal and has no holdout-eval step that writes this file. Ask: a small `classification/evaluate.py` that scores `holdout_inputs.csv` against `holdout_labels.csv` and writes `metrics.json` in the shape of `contracts/metrics.example.json`.
- Data prep now merges three source files with de-duplicated body groups (PR #7), so `dataset` should name all sources and the split sizes will change. The UI reads both from the file, so no UI change is needed.

## Coverage check
| Item | Required by | Where on the page |
|---|---|---|
| Macro-F1 for type, queue, priority | Spec §4 (required) | Accuracy table, Macro-F1 column |
| High-priority incident recall | Spec §4 (required) | Hero number + visible label |
| Holdout (20% split) metrics | Spec §3–4 (required) | Subtitle + "Holdout" fact |
| No leakage | Spec §7 (disqualification rule) | "Leakage check" fact + tooltip |
| Latency from batch eval | Pacing guide hour 4–5 (implied) | "Median latency" fact (p50/p95 in tooltip) |
| Calibrated confidence | Spec §2 "calibrated confidence score" | Calibration error column |
| EN + DE performance | Multilingual track | English / German columns |
| Escalation trade-off | Ivy's plan §7.3 | Sentence + tooltip table |
| Outcome mix, cost, model, dataset | Context | Facts row + footer |
| Draft quality | Chase's eval (optional) | Extra fact only when `drafts` is present |

## Principles (from user feedback so far)
- One reading column, read top to bottom like a short report. No grid of identical tiles.
- Each section is titled by the **question** it answers, so no captions or legends are needed to explain it.
- Say each thing once: no captions repeating a number, no unit on every value, no titles repeating a control.
- No charts or graphs. Small text tables only where they're the clearest form.
- No "More info" text, ⓘ icons or expanding panels. Extra detail goes in hover/focus tooltips on the thing it explains.
- Colour only for meaning: amber for weak values (F1 < 0.70), and status colours for the three statuses. Everything else is neutral.

## Layout (1440 px; content column max-width 880 px, centred)

```
Model metrics                                                    (24/32 semibold)
Sample data · evaluated on 4,000 holdout tickets the model never saw   (14/20 ink-3)

────────────────────────────────────────────────────────────────────────────────

Does it catch urgent incidents?                                  (17/24 semibold)

91.3%                                                            (44/48 semibold, tabular)
High-priority incident recall · 409 of 448 escalated to on-call  (15/24 ink-2)

To catch 90% of them, 26% of all tickets go to a human.          (15/24 ink)
   └ hover: trade-off table (catch rate · sent to a human · precision · tickets)

────────────────────────────────────────────────────────────────────────────────

How accurate is the triage?                                      (17/24 semibold)

               Macro-F1   Accuracy   English   German   Calibration error
Type             0.77       0.80       0.79      0.76        0.03
Queue            0.63       0.67       0.64      0.62        0.04
Priority         0.71       0.73       0.72      0.69        0.03
   └ hover a row: per-class table (class · F1 · precision · recall · tickets)
                  + "Most often confused: Problem → Incident (138)"
   └ hover a column header: one-line definition

────────────────────────────────────────────────────────────────────────────────

Is the evaluation sound, and is it fast?                         (17/24 semibold)

Holdout            Leakage check      Median latency     Cost per ticket
4,000 tickets      0 overlaps         1.48 s             $0.0009
   └ hover each: split sizes · leakage detail · p50/p95 + stage times · cost breakdown

Outcome mix   52% auto-draft · 33% human review · 15% escalated   (status-coloured words)

Model TF-IDF + LinearSVC (calibrated) · data dataset-tickets-multi-lang-4-20k.csv · updated 21 Nov, 14:00   (13/18 ink-3)
```

- Sections are separated by whitespace (40 px) and one hairline rule. No cards inside cards, and no card per number.
- The accuracy table is the only table on the page: 3 rows × 5 numbers, left-aligned labels, right-aligned numbers, column headers 13/18 medium ink-2, rows 15/24 with 12 px vertical padding and faint separators. Macro-F1 is semibold. Values < 0.70 (F1) are amber.
- The facts row has four equal columns, label above value (label 13/18 ink-3, value 17/24 medium tabular), wrapping as whole items below 900 px.
- Below 1024 px everything stays one column (it already is), and the accuracy table scrolls horizontally inside its own box if needed.

## Typography (applies to this tab; same tokens as the Console)
| Role | Size / line height | Weight | Colour |
|---|---|---|---|
| Page title | 24 / 32 | 600 | ink |
| Section question | 17 / 24 | 600 | ink |
| Hero number | 44 / 48 | 600, tabular-nums | ink (not coloured) |
| Body / sentences | 15 / 24 | 400 | ink or ink-2 |
| Table cells | 15 / 24 | 400 (Macro-F1 600), tabular-nums | ink |
| Labels, headers, meta | 13 / 18 | 500 headers, 400 meta | ink-2 / ink-3 (≥ 4.5:1) |
| Tooltip text | 13 / 20 | 400; tooltip table headers 500 | ink |

Font: Inter 400/500/600 only. No monospace on this tab. Sentence case everywhere; no all caps or letter-spacing.

## Tooltips
- One shared `Tip` component (it already exists), opening on hover **and** keyboard focus (`tabIndex=0`, `aria-describedby`) and toggling on tap.
- 360 px wide (max 420), 14–16 px padding, kept inside the viewport and never covering its own trigger (place it below; flip above near the bottom).
- Trigger affordance: a dotted underline on hoverable text and numbers, and `cursor: help`. No icons.
- Contents are text and small tables only. Tables inside tooltips use the same rules as the main table, at 13/20.

| Trigger | Tooltip content (fields) |
|---|---|
| Hero number | definition (1 line); `high_priority_incident.caught/total`; `escalation_rate` as "27% of all tickets escalated (1,080 of 4,000)" |
| Trade-off sentence | `escalation_tradeoff[]` table: catch rate · sent to a human · precision · tickets escalated |
| Accuracy row (Type/Queue/Priority) | `heads.<h>.per_class[]` table: class · F1 · precision · recall · tickets (F1 < 0.70 amber); "Most often confused: A → B (n)" from the largest off-diagonal in `confusion` |
| Accuracy column header | definition: Macro-F1 (unweighted mean of per-class F1) · Accuracy · English/German (macro-F1 on that language's holdout tickets) · Calibration error (ECE, lower is better) |
| Holdout | `split.train / knowledge_base / holdout` |
| Leakage check | `split.leakage_detail` |
| Median latency | p50 and p95 defined; `pipeline.stage_latency_ms` as a small table |
| Cost per ticket | `pipeline.cost_breakdown_usd` table plus `cost_basis` |
| Outcome mix | the counts behind each percentage (of `pipeline.tickets`) |

## States
| State | What shows |
|---|---|
| Sample data (`sample: true`) | the subtitle starts with "Sample data ·" in ink-3 with a small amber dot; nothing louder |
| Real data | the subtitle is just "Evaluated on 4,000 holdout tickets the model never saw" |
| Loading | the three section titles with grey placeholder lines (no spinner) |
| Invalid or missing file | inline message under the page title: "Metrics file is missing or invalid: <fields>", plus a Retry link |
| Optional fields missing (`drafts`, `calibration_error`, `macro_f1_by_language`, `pipeline.*`) | hide that column, row or item. No empty cells, no "N/A" |
| `drafts` present | one extra facts item, "Draft quality", with citation-valid / language-match / claims-removed rates in its tooltip |

## Acceptance criteria
- [ ] At 1440 px, all three sections are visible without scrolling at a 900 px tall viewport.
- [ ] The spec's exact metric names are visible on the page, not only in tooltips: "High-priority incident recall" and "Macro-F1" (type, queue, priority), plus "holdout" and "latency".
- [ ] No text in all caps; no "More info", ⓘ, charts, bars or expanding panels on the tab.
- [ ] Exactly one table on the page; numbers right-aligned in tabular-nums; Macro-F1 bold; values < 0.70 amber.
- [ ] Every number listed in the tooltip table shows its tooltip on hover and on Tab focus; no tooltip covers its own trigger or leaves the viewport.
- [ ] Typography matches the table above (check computed styles for the title, the section question, the hero number, a table cell and a meta label).
- [ ] Light and dark themes both readable; body and meta text ≥ 4.5:1.
- [ ] The missing-optional-field and invalid-file states render as specified (add them to `/dev/states`).
- [ ] Typecheck, build and `node ui/src/lib/validate.test.ts` pass.

## Out of scope
Charts, the confusion-matrix grid, per-ticket drilldown, live recomputation, the History tab.

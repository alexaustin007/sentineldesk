# Triage Console: build notes

Build of UI_WORKFLOW §4.1 (wireframes A–D plus the tweaks table), covering AGENT_WORKFLOW build order 0–6, against mock data only. No backend yet.

## How to run

| | |
|---|---|
| Dev (mock) | `preview_start ui-dev` (`.claude/launch.json`), or `npm --prefix ui run dev -- --port 5173`. `ui/.env.development` sets `VITE_USE_MOCK=true`. |
| Checks | `npm --prefix ui run typecheck` · `npm --prefix ui run build` (both pass) |
| All states | `http://localhost:5173/dev/states` (anchors `#entry #validation #loading #error #timeout #a #b #c #d #low #contract #unknown-status #auto-null #no-thresholds`) |
| Force failures in mock mode | `/?mock=error` (error + Retry) · `/?mock=timeout` (shows the timeout state after 30 s) |
| Live API | Run without `VITE_USE_MOCK` (the production build defaults to live). `POST /api/triage` goes through the Vite proxy to `localhost:8000`. For a mock build use `VITE_USE_MOCK=true npm --prefix ui run build`. |

Stack: Vite 6, React 18, TypeScript 5.8 (strict), Tailwind v4 (`@tailwindcss/vite`). There is no router, state or icon library (F3).

## Files

| Path | What |
|---|---|
| `ui/src/types/triage.ts` | Contract types. Labels are typed `string` so unknown values pass through. `escalation.status` is optional or any string. |
| `ui/src/lib/api.ts` | `triage()` with a 30 s `AbortController` timeout. Mock mode waits 1–2 s, then picks a mock. Parses errors as `{error:{code,message}}`. |
| `ui/src/lib/labels.ts` | `normalizeStatus` (missing/unknown → `escalate`), banner strings, confidence bands, `priorityTone`, the 5 `gateChecks`, and `reasonText` (operator wording such as "No precedent: knowledge gap"). |
| `ui/src/lib/run.ts` | Run state union: idle / loading / success / error / timeout. |
| `ui/src/mocks/*.ts` | `vpnOutage` (A), `deBilling` (B), `knowledgeGap` (C), `injection` (D), and `lowConfidence` (dev-only edge case). `index.ts` maps the 4 chips to mocks, and `pickMock` routes free text by keyword. |
| `ui/src/components/TicketInput.tsx` | Subject (optional), body, 4 chips, Triage button with ⌘/Ctrl+↵. Guardrail evidence is highlighted inside the body using a backdrop `<mark>` layer. |
| `ui/src/components/Pipeline.tsx` | Step list (classify → retrieve → generate → guardrails) with per-stage ms and total. While loading it shows estimated progress and a live elapsed timer. On failure it shows failed or timed out. |
| `ui/src/components/EscalationBanner.tsx` | Full-width banner with the spec's exact text, reason line, "paging {queue} on-call", quoted evidence, `EN · 2.14 s`, Acknowledge (UI-only, then "Acknowledged by operator · HH:MM"), and the Why? checklist (open when escalated, closed when auto-draft). |
| `ui/src/components/Classification.tsx` | Three identical rows with a bar, threshold tick, value, and High/Medium/Low. Below threshold is amber with `< 0.60`. Alternatives appear in the row tooltip. |
| `ui/src/components/DraftReply.tsx` | Inline `[TKT-xxxxx]` chips with hover popover (subject, sim, language, answer line). Click jumps to the precedent. Unknown IDs get a dashed amber chip. Header and button follow the gate. Handles `draft: null`. Shows a notice when `citations_valid: false`. |
| `ui/src/components/Precedents.tsx` | Compact rows, at most 5, sorted by similarity. Top and cited rows start expanded. `cited` tag, colourless `Likely duplicate` at ≥ 0.90, greyed rows below the similarity threshold, "Closest precedents · all below …" header. Citation hover tints the row; click expands, scrolls to it and flashes it. |
| `ui/src/components/ResultsPane.tsx` | Loading skeleton (staggered), error and timeout with Retry, and success sections revealed in B2 order. Renders nothing when idle. |
| `ui/src/components/EntryView.tsx` | Entry-only first screen: a centred card with the ticket input (`variant="entry"`). |
| `ui/src/components/{Section,PriorityLabel,Toast,Icons,ConsoleView}.tsx` | Bounded labelled region (C2), priority colouring, copy toast, inline SVG icons, and the two-pane layout shared by Console and `/dev/states`. |
| `ui/src/pages/{ConsolePage,MetricsPage,DevStates}.tsx` | Console state and shortcut, Metrics placeholder, and the states harness. The harness imports `contracts/triage_response.example.json` as a `TriageResponse`, so contract drift breaks the typecheck. |
| `ui/src/App.tsx` | Header with Console/Metrics tabs, Mock/API indicator and theme toggle, plus a pathname router. Theme follows `prefers-color-scheme` until toggled (saved in `localStorage`). |
| `ui/src/index.css` | Colour tokens for light and `.dark`: one neutral ramp, one accent (blue), and banner red/green kept apart from the muted status tones. |
| `ui/vite.config.ts` | Port 5173 strict, `/api` proxy to `:8000`, and `fs.allow: [".."]` for the contract import. |

## Acceptance (checked in the browser at 1440 px, light + dark)

- [x] Typecheck and build pass.
- [x] `ui-dev` serves on 5173.
- [x] Chip **VPN outage** gives wireframe A: escalate, `HIGH_PRIORITY_INCIDENT`, Why open with ✗ on "high priority + Incident", holding reply, "Copy as internal note", 2 precedents.
- [x] Chip **DE billing** gives wireframe B: Auto-Draft Ready, "No escalation rule triggered · DE · 1.62 s", Why collapsed, German draft with 2 chips, "Copy draft", `TKT-12093` tagged Likely duplicate, cited rows expanded.
- [x] Chip **No subject** gives wireframe C: subject is sent as `null`, "No precedent: knowledge gap (top similarity 0.31 < 0.55)", "Draft · Not generated: there is no past resolution…", "Closest precedents · all below 0.55, shown greyed", generate step shown as `skipped`.
- [x] Chip **Injection** gives wireframe D: "Prompt injection detected · Unsupported request (refund guarantee)", evidence quoted in the banner and highlighted in the body field, ✗ on both guardrail checks.
- [x] ⌘/Ctrl+Enter submits. The loading state and disabled button appear immediately (A1). Pipeline steps tick off (A2).
- [x] Empty body shows only "Body required" (D3).
- [x] Error state has code, message and Retry. Timeout appears after 30 s with Retry (A3). Verified with `?mock=error` and `?mock=timeout`.
- [x] Citation hover shows the popover and tints the precedent. Click expands, scrolls to and flashes it (C5). Chip hit area is 32 px tall via `::after` (D2).
- [x] Acknowledge changes the banner to "Acknowledged by operator · HH:MM". Copy shows a toast (E1).
- [x] Priority colours only `high`/`medium`/`low`. `critical` shows neutral grey (`#low`). Missing status and `"maybe"` both render as escalate (`#low`, `#unknown-status`). Queue is printed verbatim.
- [x] All mock precedent IDs are below `TKT-49412`: 01842, 03917, 07731, 09385, 12093, 15660, 22548, 28104, 30517, 33021, 40766. `TKT-99999` appears only as a deliberately invalid citation in `#low` and is not a precedent.
- [x] Panes stack below 1024 px with no horizontal scroll.
- [x] One primary button, 4 chips, no language picker, no "AI" styling. The banner is the only saturated fill (B1).

Screenshots were taken locally and are not committed.

## Contract gaps (for backend owners; contract not edited)

1. **Stage timings are only available at the end.** The pipeline list estimates progress while waiting. True live ticks would need SSE/streaming or a `202` plus a poll endpoint. This is optional, since the current behaviour already satisfies A2.
2. **`latency_ms.generate` when no draft is produced.** The UI treats a missing stage key as `skipped`. Please omit the key rather than send `0` when generation is skipped.
3. **Missing `escalation.thresholds`.** The UI falls back to 0.60 / 0.55 and shows an amber "thresholds missing" note in Why. Please always send them.
4. **Gate checks vs reasons.** The UI marks a check ✗ if either its own computation or the backend's `reasons[]` says so. If the backend uses a different rule (for example a non-`min` confidence rule), say so and the UI will follow `reasons[]` only.
5. **`UNSUPPORTED_REQUEST.message`** is shown in brackets when ≤ 40 chars, e.g. "(refund guarantee)". A short dedicated field such as `reasons[].detail` would be cleaner.
6. **Major-incident banner (stretch)** needs a new field, e.g. `cluster: { label, count, window_min }`. Not built.
7. **Precedent subject for the popover** is already in `precedents[].subject`. No gap.

## Known gaps / not built

- Override dropdown, outage banner, PII highlight and feedback reactions (all stretch).
- Metrics tab is a static placeholder until `metrics.json` exists.
- No leakage flag for precedent IDs ≥ split index (UI_WORKFLOW §8.6). Easy to add once the index is confirmed.
- The citation popover is anchored left and can cover the Copy button for a chip near the right edge. It doesn't clip at 1440 px.
- `simplify` skill not run. Lint not configured (no ESLint, to avoid extra deps).
- Fonts load from Google Fonts (IBM Plex Sans/Mono). Offline, they fall back to system fonts. Bundle them with `@fontsource` if the demo venue has no network.

## Visual pass + Fixes (after review loop 1)

The owner said the UI looked sparse, washed-out and generic. The changes below address that and the majors from `console.review.md` loop 1.

**Visual pass**
- Layout: the ticket input is now a full-height sticky sidebar (`bg-surface`, border-right), and results sit on the page background (max 1080 px). `/dev/states` frames each case the same way.
- Typography: IBM Plex Sans + IBM Plex Mono. Small-caps labels are now only on section headers (darker `ink-2`), and row labels are sentence case. The banner title is 20 px semibold title case.
- Banner: a tinted panel with a 6 px full-strength stripe and a round status badge, in place of the solid red/green block. Title is in a darker status shade. The stripe and badge are the only full-strength status colour (B1).
- Classification: one shared grid. Each row shows the top `alternatives[0]` as `alt X 0.06`. The header shows the threshold-tick legend.
- Draft: the footer shows "Grounded in N of M precedents" (or the `citations_valid` warning) next to the copy action.
- Precedents: two-line rows (ID + sim / subject + tags, then lang · type · priority · queue). The header shows the top sim and threshold.
- Left pane: the 4 chips are 2×2 pills with an EN/DE tag. The textarea is 7 rows. The pipeline is a stepper with a connecting line, a per-stage share-of-total bar, and an 18 px total.
- Header: nav links with `aria-current`, a check-mark logo, and a "mock data / live API" pill.

**Fixes**

| Review # | Fix |
|---|---|
| 1 (major, C4) | The three classification rows share one grid with a fixed band column. At 1024 px all bars measure 120 px with the tick at the same x. |
| 2 (major, §4.1) | Precedent rows are two-line. The subject has the full row minus ID/sim (130–200 px at 1024 px), and the tag never wraps (`whitespace-nowrap`). |
| 3 (major, contrast) | The banner text is now ink on a tint. The status title is ≥ 6.9:1 in light and ≥ 8.4:1 in dark, and no text uses opacity. |
| 4 (major, contrast) | Light `--ink-3` is `#5c5e65` (6.5:1 on surface, 5.8:1 on bg), `--amber` is `#8a5c00` (5.2:1 on bg), and section labels use `--ink-2`. |
| 5 | Greyed precedents use `text-ink-3` instead of opacity. |
| 6 | The banner is now a light tint, so the blue focus ring has normal contrast there. |
| 7 | Triage and the chips use `aria-disabled` instead of `disabled`, so focus stays put on submit. Retry moves focus to Triage. |
| 8 | On error or timeout the in-progress step shows "stopped" (not "failed"), and the total row reads "failed after / timed out after N s". |
| 9 | Removed `aria-live` from the pipeline. |
| 10 | Console/Metrics are `<nav>` links with `aria-current="page"` instead of an incomplete tabs pattern. |
| 11 | `auto_draft` with `draft: null` appends " · no draft returned" to the banner reason. |
| 12 | With zero precedents the reason reads "(no precedents retrieved)". |
| 13 | Inputs use a `--field` border (3.2:1 light, ≥ 3:1 dark). |
| 14 | Dark Triage fill is `#3d61cb` with white text (5.6:1), down from the bright `#7d9cf5`. |
| also | Long queue/subject labels get a `title` tooltip. Retry is a secondary button, so there is still exactly one primary (D1). |

Re-checked: typecheck and build pass. 1440 light and dark, and 1024 measurements (bars identical, subjects visible, no horizontal scroll). No console errors in the browser pane. Screenshots are in the shared notes folder with the `v2-` prefix.

## Entry-first flow (team request)

- **Before the first submit**, `/` shows only a centred card ("Triage a ticket") with subject, body, the 4 chips and Triage. The body is autofocused. There is no results pane and no dashed outlines. Empty-body validation happens here.
- **On submit**, the view switches to the two-pane layout. The ticket moves into the compact left pane, which stays editable and visible (C6) and has a **+ New ticket** action. Focus stays on Triage. While loading, the pipeline steps tick off and the four placeholders appear with a 120 ms stagger. The results then rise in, in order (banner → classification → draft → precedents), 90 ms apart and 220 ms each, using a CSS keyframe only. `prefers-reduced-motion` turns the motion off.
- **New ticket** cancels any in-flight request, clears the fields and returns to the entry view with the body focused.
- **Error and timeout** still render in the results pane with Retry (unchanged).
- On `/dev/states`, `#entry` and `#validation` render the entry view. The other cases still show the two-pane layout.
- Verified at 1440 px light and dark: entry, loading, result B, New ticket, and `?mock=error` with Retry. Typecheck and build pass. Screenshots are in the shared notes folder with the `v3-` prefix.

## Example tickets as quiet links (team request)

- The 4 sample pills are now one line of small text links below Triage: "Try an example: VPN outage · German billing · Injection attempt · No subject". There are no language badges, no selected or active state, and no `aria-pressed`.
- A click only fills subject and body. It never submits.
- The same line also appears in the compact left pane after submit.
- The text box and the Triage button are the only prominent controls in the entry view. Each link has a 32 px hit area (`h-8`).
- Labels changed in `ui/src/mocks/index.ts`. The mapping to the A/B/D/C mocks is unchanged.

## Fixes (review loop 2, quick)

| Finding | Fix |
|---|---|
| Major: queue label cut off at 1024 px ("Billing and Paym…") | The classification value and alt text wrap instead of truncating. The label column is `minmax(150px,1fr)` and the bar column `minmax(100px,1.3fr)`. At 1024 px "Billing and Payments" and "Returns and Exchanges" show in full, no cell clips, and all three bars are 144 px. |
| Note: one timeout run ended early with "signal is aborted without reason" | A request we cancelled ourselves (New ticket, unmount or hot reload) is now ignored instead of shown as an error. |

The loop-2 review found no blockers, and the 4 loop-1 majors are confirmed fixed. Per the team, there is no further review loop. Minors are left as listed in `console.review.md`.

## Revised contract (PR #5 + Ivy's classifier plan)

The UI now follows the revised `contracts/triage_response.example.json` and UI_WORKFLOW §3–§3.2 and §4.1 wireframe E.

- **Types** (`ui/src/types/triage.ts`):
  - `escalation.status` is `auto_draft | human_review | escalate`.
  - `input.language_supported` and `input.pii_counts` replace `pii_masked`.
  - New: `classification.{head}.margin?`, `classification.critical_incident_risk`, `classification.disagreements`, `escalation.thresholds.critical_incident_risk`, `route`, `guardrails.injection_signals`, `removed_claims`, `verification_issues`, `usage`.
  - Optional: `reasons[].code`, `precedents[].language` and `.subject`.
  - `latency_ms` has free-form stage keys.
  - The contract example still typechecks via `/dev/states#contract`.
- **Banner:** three states, each the only saturated colour while shown (B1):
  - green "Auto-Draft Ready"
  - amber "Needs Human Review" (new `--rev` tokens: text 6.5:1 light, 10:1 dark)
  - red "Escalate to On-Call Engineer"

  A missing or unknown status still renders as red escalate.
- **Reasons:** each `message` is rendered verbatim, one per line. A known `code` adds a small tag (e.g. `knowledge gap`, `injection`). `OTHER`, unknown or missing codes get no tag (`#unknown-code`, `#e`).
- **Banner meta line:** lang (plus "(unsupported)" if `language_supported: false`), route (fast/deep), end-to-end latency, and `usage.estimated_cost_usd` as `$0.0004`, hidden when 0.
- **Why? checklist:**
  - Uses `thresholds` (0.55 / 0.45). The default fallback is now 0.55 / 0.45 too.
  - Conditional rows: "critical incident risk < T" (only when the risk isn't null), "classifier vs precedents disagree on: queue" (only when `disagreements` is non-empty), "supported language" (only when it failed) and "verifier found no unsupported claims" (only with removed claims, issues or `VERIFICATION_FAILED`).
  - A margin note sits on the confidence row, and `LOW_MARGIN` fails that row.
  - Open by default for `human_review` and `escalate`.
- **Draft:**
  - `escalate` + `null` shows "No draft: paged on-call before drafting".
  - `human_review` with a draft gets the header "for human review" and "Copy as internal note".
  - `removed_claims` is listed under the draft as "Removed by verifier (unsupported): …", struck through and muted, and also shows when there is no draft.
- **Pipeline:** PR #5 stage names in order (guardrails → classifier → retrieval → adversarial review → draft reply → verification). Only stages present in `latency_ms` are shown, and unknown keys are appended. While loading it shows the five stages every routed ticket runs. A `route: fast/deep` tag sits next to the label, with the route reasons as a tooltip.
- **Precedents:** when `subject` is missing, the meta line (type · priority · queue) moves up, so there's no blank line. When `language` is missing it is dropped from the meta line and the citation popover.
- **Mocks:**
  - VPN outage → `escalate`, `draft: null`, route `none`
  - German billing → `auto_draft`, route `fast`, $0.0004
  - No subject (knowledge gap) and Injection attempt → `human_review`
  - New `humanReviewDeep.ts` (wireframe E) → `human_review` with a draft, route `deep`, disagreement on queue, one removed claim, one reason without a code, and one precedent without language/subject. It is only on `/dev/states#e`, because a fifth link would break the one line and D1's limit of 4.

  All precedent IDs are still below `TKT-49412`.
- **Verified:** typecheck and build pass. Checked at 1440 px: `#e` in light (banner, Why rows, draft with removed claim, precedent without subject) and the VPN example on `/` in dark (red, no draft, 3 pipeline stages, cost hidden). Screenshots are in the shared notes folder with the `v4-` prefix. No review loop, per the team.
- **Contract gap carried over from §3.2:** `critical_incident_risk` and margins may not reach the UI until PR #5's `TicketLabels` has slots for them. The UI hides those rows when they're null or absent.

## Expandable precedents with full evidence (team request)

Follows UI_WORKFLOW §4.1, tweaks row "Expandable precedents with full evidence", and the new optional `precedents[].body` / `.answer`.

- **Collapsed (default, nothing starts open):** ID + similarity on the left.
  - Line 1: subject, then lang · type · priority.
  - Line 2: a one-line resolution preview (`answer`, else `answer_snippet`) with the `cited` / `Likely duplicate` tags.
- **Expanded:**
  - **Original ticket:** subject and full `body`, clipped to 6 lines, with "Show more"/"Show less" when it overflows.
  - **Resolution:** full `answer`, the largest text in the panel.
  - **Label row:** type, queue, priority, language, similarity.
  - The panel is `max-h-[440px]` and scrolls internally, so the page doesn't jump.
- **One row open at a time.** Clicking a `[TKT-…]` citation opens that row, closes any other, scrolls to it and flashes it. The row header is a `<button>` with `aria-expanded` / `aria-controls`, so Enter and Space toggle it.
- **Fallbacks:**
  - no `answer` → `answer_snippet`
  - no `body` → no "Original ticket" block
  - missing `subject` / `language` → those cells drop out (the meta line takes line 1)
- **Mocks:** `body` and `answer` added to every precedent except TKT-09385 (`/dev/states#c`) and TKT-36002 (`#e`, which also lacks subject/language). TKT-01842's body is a pasted email long enough to show "Show more" (`#a`).
- **Verified at 1440 px light:**
  - German billing on `/`: nothing open at first.
  - `[TKT-40766]` opens only that row and flashes it; `[TKT-12093]` then switches to it.
  - `#a`: Show more → Show less.
  - `#c` and `#e`: the fallbacks.

  Typecheck and build pass. Screenshots have the `v5-` prefix. No review loop.

## Runtime check of the backend response (team request)

- **`ui/src/lib/validate.ts`** (hand-written, no library, F3): `parseTriageResponse(raw)`. `TriageError` now lives here and `api.ts` re-exports it. The file has no runtime imports, so Node can run its test directly.
  - **Required:** `classification.{type,queue,priority}.label` (string) and `.confidence` (number); `precedents` (array, each item with a string `ticket_id` and a numeric `similarity`); `latency_ms.total` (number). Anything missing throws `BAD_RESPONSE` "Backend response missing or invalid: <every bad path>".
  - **PR #5 raw shape:** if a `final_labels` key is present, it throws "Backend returned PR #5's raw TriageResult; the API wrapper must convert it (docs/UI_WORKFLOW.md §3.2)".
  - **Normalized instead of failing:**
    - A missing or unknown `escalation` / `status` becomes `escalate`, with an `OTHER` reason "Backend sent no escalation decision; treated as escalate" placed before any backend reasons.
    - `reasons` → `[]`; `thresholds` → 0.55 / 0.45 / null.
    - `guardrails` flags and lists → `false` / `[]`; `draft` → `null`.
    - `input.language_detected` → `"en"`, with a UI-only `language_missing` flag that hides the lang badge.
    - `route` → `none`, `usage` → omitted, `disagreements` → `[]`.
    - Confidences and the risk score are clamped to 0–1.
  - The file came out at 95 lines, over the 40–60 asked for, because it normalizes every optional field explicitly.
- **Wiring:**
  - `liveTriage` parses `res.json()` through the validator; a non-JSON body becomes `BAD_RESPONSE` too.
  - In dev builds (`import.meta.env.DEV`) the mock path goes through it as well.
  - New `/?mock=raw` returns the PR #5 raw shape, for demo testing.
- **Error state:** the existing error pane (A3) shows the message, the `BAD_RESPONSE` code and Retry, with the title "Unexpected backend response".
- **`/dev/states`:** `#bad-response` (wrong types, every path listed), `#raw-pr5-shape` and `#normalized` (a minimal valid response: red escalate with the OTHER reason, no lang badge, confidences clamped). All three run through the real validator.
- **Test:** `node ui/src/lib/validate.test.ts` (Node ≥ 22.18 strips types; no framework, no `tsx`) runs 12 checks: the contract example, the raw shape, path listing, non-object body, normalization defaults, unknown status, and all 6 mocks. All pass. The test is excluded from `tsc` in `ui/tsconfig.json` because it uses `node:assert`.
- **Verified:** typecheck and build pass. At 1440 px, `/?mock=raw` on the console shows the error with Retry; `#bad-response`, `#raw-pr5-shape` and `#normalized` render as described. Screenshots have the `v6-` prefix. No review loop.

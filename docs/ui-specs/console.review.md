# Triage Console: review

Graded against UI_WORKFLOW §1, §3.1, §4.1 (wireframes A–D and the tweaks table) and §5, and every Check in UX_RULES. There is no planner spec (`console.md`). Each item below was checked in Chrome (DevTools MCP, true 1440 px viewport) against the mock dev server on :5173. Claims in `console.build.md` were re-tested, not assumed.

Screenshots were taken locally and are not committed.

## Loop 1

### Findings

| # | severity | rule / criterion | what you saw (screenshot ref) | concrete fix |
|---|---|---|---|---|
| 1 | major | C4 (identical confidence bars), B4 | Between 1024 px and about 1240 px (two-pane), and at every stacked width, the three bars have different widths and threshold-tick positions. TYPE vs QUEUE/PRIORITY at 1024 px: x 729/719, width 158/148 px, tick 823/806 px. At 1152 px: width 234/214. At 768 px: width 270/250. The cause is that each `Row` is its own grid and the last column is `auto`, so "High" and "Medium" give different tracks. At 1280+ the bars are identical. `review-B-1024-light.png` | Put the three rows in one grid container so they share tracks (one `grid` with `grid-template-columns` on the parent, or `grid-cols-subgrid`), or give the band column a fixed width (e.g. `88px`, which fits "Low < 0.60"). |
| 2 | major | §4.1 "Compact precedent rows" (ID, sim, lang, type · priority, **subject**), B4 | At 1024 px two-pane the subject column collapses. The top precedent `TKT-12093` subject is **0 px wide** (invisible), `TKT-40766` shows "Charged t…" (77 px), and the "LIKELY DUPLICATE" tag wraps onto two lines. At 1152 px the top subject is 75 px. `review-B-1024-light.png` | Give the subject a real minimum (`minmax(120px,1fr)`) and let the row wrap below ~640 px of pane width. For example, move `type · priority` and the tags onto a second line, or hide `type · priority` under a container query. Add `whitespace-nowrap` to the tag. |
| 3 | major | B1 / §5 (decision banner must read as the decision; "readable on a projector"), WCAG 1.4.3 | **Dark theme, auto-draft banner:** white on `--ok #1f8a4e` is **4.37:1** for the 16 px bold title "AUTO-DRAFT READY", the 14 px reason line and "Why?". The `opacity-90` meta line "DE · 1.62 s" is **3.85:1**. Lighthouse flags all 4 nodes. **Dark, escalate banner:** the `opacity-85` "· paging … on-call" span is **4.29:1**. `review-B-1440-dark.png`, `review-A-1440-dark-ack.png` | Dark `--ok` → `#17733f` (5.9:1) or `#1a7a45` (5.4:1). Remove the opacity on banner sub-text (or keep it ≥ 0.95), so every banner line is ≥ 4.5:1 in both themes. |
| 4 | major | C2 (section label must be visible) + §4.1 "readable on a projector", WCAG 1.4.3 | **Light theme:** `--ink-3 #7a7c83` is **4.16:1** on surface and **3.85:1** on bg. It is used for every small-caps 11 px section label (TICKET, SAMPLES, PIPELINE, CLASSIFICATION, WHY · GATE CHECKS, TYPE/QUEUE/PRIORITY, PRECEDENTS), "(optional)", the inactive Metrics tab, "Mock data", the Why values and the pending pipeline steps. Lighthouse lists 20 nodes. The only validation message, "Body required" (`--amber` on bg), is **4.38:1**. `review-A-1440-light.png`, `review-validation-1440-light.png` | Light `--ink-3` → `#686a71` (5.4 on white, 4.99 on bg, 4.73 on surface-2). Light `--amber` → `#8a5f00` (5.65 on bg). Dark `--ink-3` already passes (4.75 / 5.02). |
| 5 | minor | WCAG 1.4.3 (spec asks for "shown greyed") | Precedents below the similarity threshold use `opacity-55`. Text drops to 2.0:1 (lang), 2.7:1 (type) and 3.8:1 (subject) in light, and 2.3–5.2:1 in dark. `review-C-1440-light.png` | Grey with a token colour (`text-ink-3` at full opacity, with the fix from #4) instead of whole-row opacity. |
| 6 | minor | Keyboard / WCAG 2.4.7 | The global `:focus-visible` ring is `--accent` blue, so on the red and green banner it is about 1.2:1 against the fill. It is visible on "Why?" and "Acknowledge", but faint. `review-focus-why-on-banner-light.png` | Inside the banner use `outline-color: currentColor` (white), or a 2 px white ring with an offset. |
| 7 | minor | Keyboard | Submitting from a sample chip disables the chip, so focus drops to `<body>`. Clicking Retry unmounts the Retry button and focus is lost again. The next Tab resumes from the old position, which works, but nothing is focused. | After submit, keep focus on the Triage button. After results load, consider focusing the banner (`tabIndex=-1`). After Retry, focus the Triage button. |
| 8 | minor | A2 / E2 (honest progress) | In error and timeout states the "failed" mark is placed on an **estimated** stage: anything after 700 ms shows "generate failed", and a fast NETWORK error would show "classify failed". The backend never said which stage failed. `review-error-timeout-1440-dark.png` | On error, mark the step that was active as "stopped", or put the failure on the total row ("failed after 0.82 s") unless the error body names a stage. |
| 9 | minor | a11y (screen reader) | The Pipeline wrapper is `aria-live="polite"` and its "total" re-renders every 100 ms while loading, which makes screen readers chatter. | Drop `aria-live` from the pipeline, or limit it to step changes. The banner's `role=status` already announces the result. |
| 10 | minor | E1 / ARIA tabs | Console/Metrics use `role=tab` but there is no `tabpanel`/`aria-controls`, both tabs are separate Tab stops, and arrow keys do nothing. | Either use the full tabs pattern (roving `tabIndex`, arrow keys, `tabpanel`) or plain `<nav>` links with `aria-current="page"`. |
| 11 | minor | §3.2 rule (draft may be null when escalated), D3 | `#auto-null`: the banner says "Auto-Draft Ready" while the Draft section says "Not generated: the generator returned no draft." The decision and the action contradict each other. This would be a contract violation from the backend, but the UI shows it as-is. | When `status=auto_draft` and `draft=null`, append " · no draft returned" to the banner reason line, or treat it as escalate (fail safe, like an unknown status). |
| 12 | minor | Wording | `#no-thresholds` (zero precedents) reads "No precedent: knowledge gap (top similarity n/a < 0.55)". | When there are no precedents, say "(no precedents retrieved)". |
| 13 | minor | WCAG 1.4.11 | Subject and Body field borders (`--line-strong`) are 1.66:1 (light) and 1.63:1 (dark) against their surroundings. | Use about `#8f9098` light / `#5a5d64` dark for input borders only. |
| 14 | minor | B1 (builder asked for a check) | In dark mode the Triage button is a large bright `#7d9cf5` fill. It does not use the banner colours, so the B1 Check passes as written, but it is the second-loudest element on screen. `review-B-1440-dark.png` | Optional: tone the dark accent fill down to about `#5b7fe0`, keeping text at ≥ 4.5:1. |

### Verified working (seen in the browser)

- **Wireframe A** (VPN chip): Escalate banner with the exact §3.1 string, "High-priority Incident · paging Technical Support on-call", "EN · 2.14 s", and Why open with ✗ on "high priority + Incident". Draft header reads "holding reply for engineer review", the button is "Copy as internal note", and there are 2 cited precedents, both expanded. `review-A-1440-light.png`
- **B** (DE billing): "Auto-Draft Ready / No escalation rule triggered", Why collapsed, German draft with 2 chips, "Copy draft", `TKT-12093` tagged Likely duplicate, cited rows expanded, uncited `TKT-07731` collapsed. `review-B-1440-light.png`
- **C** (No subject): knowledge-gap wording, draft "Not generated…", "Closest precedents · all below 0.55, shown greyed", generate shown as `skipped`. `review-C-1440-light.png`
- **D** (Injection): both reasons appear, evidence is quoted in the banner and highlighted in the body field, and ✗ shows on both guardrail checks. The highlight stays aligned after scrolling a long body. `review-D-1440-light.png`, `review-edge-long-injection-scroll-light.png`
- **A1 / A2:** the loading skeleton, "Triaging…" text and disabled button appear straight away. Step list: spinner on the active step, ticks on finished steps. `review-loading-1440-light.png`
- **A3:** `?mock=error` shows the code, the message and Retry, and Retry re-runs the request. `?mock=timeout` shows "No response after 30 s", TIMEOUT, Retry and "generate timed out · 30.00 s". Both keep the input.
- **C5:** hovering `[TKT-01842]` shows a popover (ID, sim, lang, subject, answer) and tints the precedent row. Clicking `[TKT-30517]` scrolled to it and applied `.flash` (accent-soft background). Keyboard focus also opens the popover. `review-A-citation-hover-1440-light.png`
- **D2:** ⌘+Enter and Ctrl+Enter both submit from anywhere. Hit areas: Triage 400×44, sample chips 197×32, Copy 179×32, Acknowledge 109×32, Why 68×32, theme toggle 32×32, citation chip 16.5 px tall + 16 px `::after` = 32.5 px.
- **D3:** an empty body shows only "Body required", focuses the body and sets `aria-invalid`. Submitting with an empty subject works. A 5,000-character body with pasted email headers and a 330-character subject gives no overflow (scrollWidth equals the viewport) and no errors. `review-edge-5000chars-1440-light.png`
- **E1:** the copy toast reads "Copied as internal note" / "Draft copied". Acknowledge changes to "Acknowledged by operator · HH:MM". `review-A-1440-dark-ack.png`
- **E3:** a threshold tick is drawn on every bar. Below-threshold values show amber with "Low < 0.60" (`#low`). `critical` priority shows as neutral grey. A missing status and `"maybe"` both render as Escalate. `review-low-1440-dark.png`
- **C1/C2/B2/B3/D1/D4/D5/C6:** 4 bounded, labelled sections in the order decision → classification → draft → precedents. One primary button, 4 chips, no language picker, no help paragraph. The input is kept after submit. Two panes from 1024 px; stacked at 900 and 768 px with no horizontal scroll (`review-B-900-dark-stacked.png`).
- **Missing thresholds + zero precedents** (`#no-thresholds`): amber "thresholds missing" note, "No precedents retrieved.", no crash. `review-no-thresholds-1440-light.png`
- **Runtime errors:** no console errors or warnings on `/`, `/dev/states`, `?mock=error`, `?mock=timeout` or `/metrics` in any run.

### Contrast and accessibility

| Pair | Light | Dark | Needed |
|---|---|---|---|
| Banner text, escalate (white on `--esc`) | 6.57 | 5.37 | 4.5 |
| Banner "paging …" (`opacity-85`) on `--esc` | 5.11 | **4.29** | 4.5 |
| Banner meta line (`opacity-90`) on `--esc` | 5.58 | 4.63 | 4.5 |
| Banner text, auto-draft (white on `--ok`) | 5.90 | **4.37** | 4.5 |
| Banner meta line (`opacity-90`) on `--ok` | 5.12 | **3.85** | 4.5 |
| Priority `high` text (`--tone-high`) on surface | 5.82 | 6.69 | 4.5 |
| Priority `medium` (`--tone-medium`) | 5.31 | 8.36 | 4.5 |
| Priority `low` (`--tone-low`) | 5.08 | 7.85 | 4.5 |
| Below-threshold amber text on surface | 4.73 | 9.08 | 4.5 |
| "Body required" amber on bg | **4.38** | 9.59 | 4.5 |
| Amber bar fill on track (non-text) | 3.82 | 7.15 | 3.0 |
| Neutral bar fill on track (non-text) | 5.74 | 5.94 | 3.0 |
| Section labels `--ink-3` on surface / bg | **4.16 / 3.85** | 4.75 / 5.02 | 4.5 |
| Citation chip (accent on accent-soft) | 4.99 | 5.36 | 4.5 |
| Triage button text on accent | 5.90 | 7.15 | 4.5 |
| Greyed precedent text (`opacity-55`) | **2.0–3.8** | **2.3–5.2** | 4.5 |
| Input border vs surface (non-text) | **1.66** | **1.63** | 3.0 |

- **B1:** the only full-strength red or green is the banner. Elsewhere red appears only as muted `--tone-high` text and ✗ icons. The B1 Check passes.
- **Focus order** (keyboard only, `/`): SentinelDesk → Console → Metrics → theme → Subject → Body → 4 chips → Triage → Acknowledge → Why? → `[TKT-01842]` → `[TKT-30517]` → Copy → precedent rows. The order is logical and every stop shows a 2 px outline (faint on the banner, see #6). A full keyboard-only triage (Tab to chip, Enter, ⌘+Enter) worked.
- **Labels:** every button has an accessible name (`read_page`). The theme toggle has `aria-label`. Fields are labelled by `<label for>`. Bars are `role=meter` with an `aria-label`. Expandable rows and Why? expose `aria-expanded`.
- **Tap targets:** all interactive controls on the console are ≥ 32 px (see D2 above).
- **Lighthouse accessibility:** **97** (light, escalate result, 20 contrast nodes) and **97** (dark, auto-draft result, 4 contrast nodes, all on the green banner). Both were snapshot mode on `/` at 1440 px.

### Feedback latency (A1)

Clicking Triage changes the DOM (`aria-busy`, "Triaging…", button disabled) **6.7 ms** after the click event, and the change is painted within **14–30 ms** (double-rAF, 4 runs). The DevTools trace recorded INP of **55–90 ms**, but it attached to a `/dev/states` target, so treat that number as indicative only. Both are well under 400 ms. The mock result arrived after 1.32 s.

### Not verified

- Live API mode (`VITE_USE_MOCK` off). Not run, because the `api/` work is in progress in another session.
- Long queue names in the Classification row. No mock has one, and code was not edited to inject one. From reading the code, the label column truncates without a `title` attribute.
- The `/metrics` placeholder renders its headings and "—" values. It is stretch scope, so it was not graded beyond that.

**FAIL**

## Loop 2 (quick)

Time-boxed pass, main console `/` only, blockers and majors only. Captures were taken with DevTools emulation at 1440x900 and 1024x800, in light and dark. Screenshots are in the side-session notes folder with the `review2-` prefix. Note: the builder was editing live during this pass. The sample chips changed from 2×2 pills above Triage to a "Try an example:" link row below Triage between captures. This review grades the later version.

| # | severity | rule | what you saw | fix |
|---|---|---|---|---|
| 1 | major | §4.1 (readable at 1024), same class as loop-1 #2 | At 1024 the Classification label column is 130 px, and the queue value is cut off: "Billing and Paym…" (needs 146 px) and "Returns and Exc…". The alt line is cut too ("alt Customer Servi…"). A `title` tooltip exists, but the routed queue is the main classification output, and it is unreadable on two of the four demo samples. 1440 is fine. `review2-B-1024-light.png`, `review2-D-1024-dark.png` | Let the label column size to its content (`minmax(130px, max-content)`) and give the space back from the bar column (bars can go to about 100 px), or let the value wrap to 2 lines instead of truncating. |

### Loop-1 majors re-checked

- **#1 bar alignment at 1024:** fixed. All three meters are x=679, w=132, h=10, with the tick at the same x.
- **#2 precedent subject at 1024:** fixed. The two-line rows show full subjects ("Doppelte Abbuchung im Oktober", "Charged twice for subscription"). The page is 1024 wide with no horizontal scroll.
- **#3 dark banner contrast:** fixed. A script check of every text node in `main` (opacity blended) found no text under 4.5:1 (or 3:1 for large text) for the escalate (injection) banner in dark at 1024 or the auto-draft banner in dark at 1440.
- **#4 light `ink-3`:** fixed. `--ink-3` is `#5c5e65`, and the same scan found no failing text on the auto-draft result in light at 1440.

### New flow verified (seen)

- **Entry view:** a centred card with Subject, Body, 4 samples and one primary Triage. There is no empty results pane. `review2-entry-1440-light-b.png`, `review2-entry-1024-dark.png`
- **On submit:** the layout switches at once to two panes. The "Triaging…" button state and `aria-busy` appear 20 ms after the click, with section skeletons (Decision, Classification, Draft) and a pipeline stepper with a spinner on the active step. `review2-loading-1440-light.png`. Results then render decision → classification → draft → precedents, and steps tick off with per-stage ms.
- **C6 (with results):** the ticket pane stays visible and editable, with input kept, at 1440 and 1024.
- **New ticket:** returns to the entry view with fields cleared and focus on Body.
- **Other checks:** ⌘+Enter submits (D2). Citation `[TKT-40766]` click scrolls to the precedent and flashes it (C5). Copy shows the "Draft copied" toast (E1). The B1 check holds: the stripe and badge are the only full-strength status colour.
- **A3:** `?mock=error` shows "Triage failed" + UPSTREAM_UNAVAILABLE + Retry, the pipeline shows "stopped", and the input is kept. `review2-error-1024-dark.png`. `?mock=timeout` shows "No response after 30 s" + TIMEOUT + Retry at about 30 s.
- **Console:** no errors or warnings on `/` in this pass.

### Not verified / not reproduced

- One `?mock=timeout` run, in a background tab while the builder was hot-reloading, ended after 2.08 s with "signal is aborted without reason · CLIENT" (`review2-timeout-1440-light.png`). Two later runs (Retry, and a fresh load + submit) behaved correctly, so this is probably an HMR artifact. It is not graded, but worth one re-run before the demo.
- Lighthouse, perf trace and keyboard-only walk-through were not re-run (time box). Loop-1 results stand.

**FAIL**

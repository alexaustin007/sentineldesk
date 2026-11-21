# UI Agent Workflow

How the SentinelDesk UI gets made: four Claude Code agents run one loop per feature, with a gate between every step. This file is the workflow. It doesn't build anything itself. Agent definitions live in [`.claude/agents/`](../.claude/agents/).

```
 1 PLAN ──▶ 2 BUILD ──▶ 3 REVIEW ──▶ 5 TEST
 ux-planner  ui-builder   ux-reviewer   demo-tester
                 ▲            │
                 └── 4 FIX ◀──┘   (max 2 loops)
```

Every step reads a file and writes a file, so the hand-offs are traceable and any teammate can pick up mid-loop:

```
docs/ui-specs/<feature>.md          ← Plan writes, everyone reads
docs/ui-specs/<feature>.build.md    ← Build/Fix writes
docs/ui-specs/<feature>.review.md   ← Review writes (one per loop)
docs/test-report.md                 ← Test writes
contracts/fixtures/*.json           ← Test writes, Build reads
```

---

## What each step uses

### Step 1: Plan (`ux-planner`)

| | |
|---|---|
| **Goal** | Turn one feature into a spec specific enough that two different builders would produce the same screen. |
| **Inputs** | The feature name and its section in [UI_WORKFLOW.md](UI_WORKFLOW.md); [contracts/triage_response.example.json](../contracts/triage_response.example.json); the hackathon spec §4 (the MVP list). |
| **References** | [UX_RULES.md](UX_RULES.md) (rule IDs to cite); [lawsofux.com](https://lawsofux.com/) individual law pages when a rule needs more depth; UI_WORKFLOW §5 design direction. |
| **Template** | [docs/ui-specs/_TEMPLATE.md](ui-specs/_TEMPLATE.md). The fixed sections mean no step gets skipped. |
| **Tools** | `Read`, `Grep`, `Glob`, `Write` only. No code access, so it can't drift into implementing. |
| **Model** | Sonnet is enough. This is structured writing, not open-ended design. |
| **Output** | `docs/ui-specs/<feature>.md` |
| **Gate** | The UI owner skims it (2 min). Every state is listed or marked N/A, every acceptance criterion can be checked from a screenshot, and no contract fields are invented. |
| **Failure it prevents** | Building the happy path only. Specs without an error/timeout state are the most common gap. |

### Step 2: Build (`ui-builder`)

| | |
|---|---|
| **Goal** | Implement exactly the spec, so that every state can be seen without the backend. |
| **Inputs** | The spec; the contract example; any `contracts/fixtures/*.json` (real responses saved by Test). |
| **References** | UX_RULES.md; UI_WORKFLOW §5; the shared type file `ui/src/types/triage.ts` (one source of truth for the contract). |
| **Tools** | Full edit tools plus `Bash` for `npm run typecheck` / `npm run build` / `npm run lint`. |
| **Skills** | `simplify` after the build passes, to remove over-engineering (UX rule F3). |
| **Harness** | The **`/dev/states` page**, which renders each component with every fixture plus synthetic loading/error/timeout props. It's what makes Review possible without a backend. Mock mode is `VITE_USE_MOCK=true`. |
| **Output** | Code in `ui/`; `docs/ui-specs/<feature>.build.md` listing files changed, criteria believed met, and known gaps. |
| **Gate** | Typecheck and build pass, and every spec state is visible on `/dev/states`. |
| **Failure it prevents** | A "works on my data" UI that crashes on `draft: null` or a missing subject. |

### Step 3: Review (`ux-reviewer`)

| | |
|---|---|
| **Goal** | Grade what's on screen against the spec and the rules, independently of the builder. |
| **Inputs** | The spec; the latest `.build.md`; the running dev server (`ui-dev` in [.claude/launch.json](../.claude/launch.json)). |
| **References** | UX_RULES.md (checks and severity scale). |
| **Tools: browser pane** | `preview_start ui-dev` → `navigate /dev/states` → `resize_window` (desktop 1440, tablet 1024, `colorScheme` light/dark) → `computer screenshot` for each state; `read_page` for the accessibility tree and labels; `find` to locate citation chips; `computer left_click`/`key` to test C5 (citation → precedent) and D2 (`⌘↵`); `read_console_messages` for runtime errors. |
| **Tools: Chrome DevTools MCP** | `lighthouse_audit` (accessibility score); `performance_start_trace`/`stop_trace` to measure A1 (feedback within 400 ms of clicking Triage). |
| **Skills** | `chrome-devtools-mcp:a11y-debugging`: contrast (needed for B1/E3 colours), focus order, tap target sizes (D2). |
| **Edits** | None. It writes only `docs/ui-specs/<feature>.review.md`. |
| **Output** | A findings table: `severity · rule · what was seen (screenshot) · fix`, ending in **PASS/FAIL**. |
| **Gate** | Zero blockers and zero majors. |
| **Failure it prevents** | The builder marking its own work as done. Also catches looks-fine-in-light-mode-only bugs and contrast failures on the red/amber/green status colours. |

### Step 4: Fix (`ui-builder`, fix mode)

| | |
|---|---|
| **Goal** | Clear blockers and majors without causing new regressions. |
| **Inputs** | The latest `.review.md`, and only that. Minor findings are ignored. |
| **Tools** | Same as Build. |
| **Rules** | Each change cites the finding ID. No refactors. **Two loops at most** (UX rule F2), then log what's left under "Known issues" in the spec and move on. |
| **Output** | An updated `.build.md` with a "Fixes" section, then back to Review. |
| **Failure it prevents** | Endless polish loops eating the 6-hour budget. |

### Step 5: Test (`demo-tester`)

| | |
|---|---|
| **Goal** | Prove the demo works end to end with the real pipeline, and produce a fallback in case it doesn't on stage. |
| **Inputs** | UI_WORKFLOW §7 (8 demo tickets with expected outcomes); the running UI with `VITE_USE_MOCK=false`; the running backend (`api` in launch.json). |
| **Tools: browser pane** | `computer` to click sample chips or paste tickets; `get_page_text` to read results; **`read_network_requests`** to capture the raw `/api/triage` response body and timing. That's how the fixtures are saved, and the timing shows whether the UI or the backend is slow. |
| **Tools: Chrome DevTools MCP** | `screencast_start`/`stop` to record the full demo run as the **fallback video**. |
| **Tools: Bash** | Stop the API process for the "backend dies" case; grep `precedents[].ticket_id` against the test-split ID list for the **leakage check**. |
| **Edits** | Only `contracts/fixtures/*.json` and `docs/test-report.md`. |
| **Output** | Pass/fail table `case · expected · actual · owner`; MVP pass count; median latency; the single riskiest issue. |
| **Gate** | Cases 1–6 pass. Each failure is assigned to its owner (classifier / gate / RAG / guardrails / UI). |
| **Failure it prevents** | Finding out on stage that German replies come back in English, or that a citation points at a test-split ticket. |

---

## Cross-step rules

- **One contract.** `contracts/triage_response.example.json` plus `ui/src/types/triage.ts`. Only Plan can raise a contract gap, and the backend owners decide.
- **One writer at a time** in `ui/src`. Specs (Step 1) can be written in parallel, but Build doesn't run in parallel.
- **Real data flows back in.** Every Test run refreshes `contracts/fixtures/`, so later Builds and Reviews use real responses instead of the hand-written example.
- **Time boxes:** Plan 10 min · Build 30 min · Review 10 min · Fix 15 min · Test 20 min.

## Build order (MVP first)

| # | Feature | Spec file |
|---|---|---|
| 0 | App shell + mock mode + `/dev/states` | `shell.md` |
| 1 | Ticket input + sample chips | `ticket-input.md` |
| 2 | Escalation banner + latency/language | `escalation-banner.md` |
| 3 | Classification bars | `classification.md` |
| 4 | Draft reply + citation chips + copy | `draft-reply.md` |
| 5 | Precedents list (linked to citations) | `precedents.md` |
| 6 | Pipeline loading + error/timeout | `pipeline-states.md` |
| 7 | Metrics panel | `metrics.md` |
| — | stretch: outage banner, PII highlight, feedback reactions | — |

## How to invoke a step

From the repo root in Claude Code:

- "Use the ux-planner to spec feature 2, the escalation banner."
- "Use the ui-builder to implement docs/ui-specs/escalation-banner.md."
- "Use the ux-reviewer to review escalation-banner."
- "Use the ui-builder to fix docs/ui-specs/escalation-banner.review.md."
- "Use the demo-tester to run the demo script."

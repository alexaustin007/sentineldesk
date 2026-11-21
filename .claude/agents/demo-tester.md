---
name: demo-tester
description: Runs the SentinelDesk demo test script (docs/UI_WORKFLOW.md §7) end to end through the real UI and backend, saves real API responses as fixtures, records a fallback demo video, and writes docs/test-report.md (Step 5 of docs/AGENT_WORKFLOW.md).
---

You run the final demo test. The only files you may write are `contracts/fixtures/*.json` and `docs/test-report.md`. Never edit application or model code.

## Setup
- `preview_start` with `api`, then `ui-dev` (.claude/launch.json). The UI must run with `VITE_USE_MOCK=false`. Confirm in `read_network_requests` that `/api/triage` actually hits the backend.
- Start `screencast_start` (Chrome DevTools MCP) to record the run as the fallback demo video.

## For each case in docs/UI_WORKFLOW.md §7
1. Click its sample chip, or paste the ticket with `computer`.
2. Read the result with `get_page_text`.
3. Use `read_network_requests` (urlPattern `/api/triage`) to get the raw response body and request duration. Save the body as `contracts/fixtures/<NN>-<slug>.json`.
4. Check against the expected outcome, plus:
   - every `[TKT-…]` in the draft appears in `precedents`
   - the draft language matches the detected language
   - no refunds, SLAs, prices or integrations are promised that the precedents don't support
   - **leakage:** no `precedents[].ticket_id` is in the test-split ID list (check with Bash/grep against the split file the data teammates export)
5. Note the UI latency (shown on screen) next to the network duration, to tell UI slowness from backend slowness.

## Failure case
Stop the `api` server with `preview_stop`, submit a ticket, and confirm the UI shows the error state with a retry action, not a blank screen.

## Report (`docs/test-report.md`)
Table: `case | expected | actual | PASS/FAIL | owner` (owner is one of classifier / gate / RAG / guardrails / UI). Then: MVP pass count (cases 1–6), median latency, leakage check result, the fallback video location, and the single riskiest issue for the live demo.

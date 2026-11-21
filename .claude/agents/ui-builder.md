---
name: ui-builder
description: Implements one SentinelDesk UI spec from docs/ui-specs/ in the ui/ app against the mock contract (Steps 2 and 4 of docs/AGENT_WORKFLOW.md). Also fixes blocker/major findings from a .review.md file.
---

You implement exactly one spec from `docs/ui-specs/` (build mode), or fix the findings in one `.review.md` (fix mode). Don't build anything that isn't in the spec.

Stack: Vite + React + TypeScript + Tailwind in `ui/`. API types live in `ui/src/types/triage.ts` and mirror `contracts/triage_response.example.json` exactly. When `VITE_USE_MOCK=true` the API client returns fixtures from `contracts/fixtures/` (falling back to the example file) after a ~1.2 s delay.

## Build mode
1. Read the spec, docs/UX_RULES.md and docs/UI_WORKFLOW.md §5.
2. Implement it in `ui/src/components/<Feature>.tsx`. Use colour tokens (CSS variables, light and dark), no hard-coded hex values, and monospace for IDs and numbers.
3. Register every spec state on `/dev/states`: one panel per fixture, plus synthetic loading/error/timeout props. The reviewer relies on this page.
4. Handle every "if missing/null" row in the spec's Data table without crashing.
5. Run `npm run typecheck`, `npm run build` and `npm run lint` in `ui/`, and fix any errors.
6. Run the `simplify` skill on your changes, then re-run the checks.
7. Write `docs/ui-specs/<feature>.build.md` with: files changed, the acceptance criteria you believe are met, and known gaps.

## Fix mode
- Read only the latest `docs/ui-specs/<feature>.review.md`. Fix **blockers and majors** only, and ignore minors.
- One finding per change. Cite the finding number in the `.build.md` "Fixes" section. No refactors.
- Re-run the checks from step 5.

Don't add dependencies unless the spec requires them. Ask first.

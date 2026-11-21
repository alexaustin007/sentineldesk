# SentinelDesk UX Rules

These rules come from [Laws of UX](https://lawsofux.com/), turned into checks for this product. Every UI agent reads this file: the planner cites rule IDs in specs, the builder follows them, and the reviewer checks them one by one.

Only laws that change a decision in this product are included. Each rule has a **Check** that you can verify by looking at a screenshot or the code.

## A. Speed and feedback

| ID | Law | Rule for SentinelDesk | Check |
|---|---|---|---|
| A1 | Doherty Threshold (<400 ms) | Show feedback within 400 ms of pressing Triage, even though the full pipeline takes seconds. | The loading/pipeline state appears straight away with no blank gap. The button shows its disabled state on click. |
| A2 | Goal-Gradient / Zeigarnik | Show the pipeline as steps (classify → retrieve → generate → guardrails) that tick off as they complete, so the wait reads as progress. | A step list is visible while loading. Finished steps look different from pending ones. |
| A3 | Peak-End Rule | The final view (the draft with highlighted citations) and the error states have to look finished. A failure must not end in a blank screen. | Error and timeout states have a message plus a retry action. |

## B. Attention and hierarchy

| ID | Law | Rule | Check |
|---|---|---|---|
| B1 | Von Restorff Effect | The escalation banner is the **only** high-saturation element on screen. Escalate = red, auto-draft = green. | Nothing else on screen uses the banner's colours at full strength. |
| B2 | Serial Position Effect | Put the decision first (banner) and the action last (draft + copy). Evidence goes in between. | Results read top to bottom: banner, classification, draft, precedents. |
| B3 | Selective Attention | No decorative elements in the results pane: no illustrations, sparkles or "AI" badges. | Every element in the results pane maps to a contract field. |
| B4 | Aesthetic-Usability Effect | Spacing, alignment and type scale are consistent, because a polished look makes judges trust the output. | One spacing scale, one type scale. Numbers are monospace and right-aligned. |

## C. Grouping and structure

| ID | Law | Rule | Check |
|---|---|---|---|
| C1 | Chunking / Miller's Law | Results come in at most 5 labelled sections. Show at most 5 precedents. | Count the sections and precedents. |
| C2 | Law of Common Region | Each section sits inside one clearly bounded region with a sentence-case heading (no all caps). | Every section has a visible boundary or background and a label. |
| C3 | Law of Proximity | Each confidence value sits right next to its label, and the reason sits right under the escalation status. | No value is detached from what it describes. |
| C4 | Law of Similarity | All three confidence bars (type, queue, priority) look identical, so they're easy to compare. | Same height, scale, threshold tick and number format for all three. |
| C5 | Law of Uniform Connectedness | A citation `[TKT-x]` in the draft is visibly connected to its precedent: hovering or clicking highlights both. | Clicking a citation scrolls to and highlights the matching precedent. |
| C6 | Working Memory | The ticket being triaged stays visible next to the results, so the operator never has to remember it. | A two-pane layout at ≥1024 px. The input isn't cleared after submit. |

## D. Decisions and input

| ID | Law | Rule | Check |
|---|---|---|---|
| D1 | Hick's Law / Choice Overload | There's one primary action (Triage). No settings, model pickers or toggles in the main flow. Show at most 4 sample chips. | Exactly one primary button. ≤4 chips. |
| D2 | Fitts's Law | The Triage button is large, sits directly under the body field, and also works with `⌘/Ctrl+Enter`. Citation chips and copy have ≥32 px hit targets. | Measure the hit areas. The shortcut works. |
| D3 | Postel's Law | Accept messy input: an empty subject, pasted email headers, mixed language, very long bodies. Show validation only for an empty body. | Submitting with no subject works. The only validation error is "body required". |
| D4 | Tesler's Law | The system takes on the complexity: it detects language automatically and the user never picks a language or queue. | No language selector on screen. |
| D5 | Paradox of the Active User | No instructions or onboarding. Sample chips teach by example. | No paragraph of help text. Chips fill the form in one click. |

## E. Familiarity and meaning

| ID | Law | Rule | Check |
|---|---|---|---|
| E1 | Jakob's Law | Use standard patterns: tabs for Console/Metrics, an icon+label copy button, a toast on copy. | No made-up controls where a standard one exists. |
| E2 | Mental Model | Match an operator's inbox model: ticket → decision → reply → evidence. Use the support team's words: "Escalate", "Draft", "Precedent". | Labels avoid ML jargon in the main view. Logits, embeddings etc. appear only in Metrics. |
| E3 | Cognitive Load | Confidence shows as a bar with the gate threshold drawn on it, not as a bare number. Values below the threshold turn amber. | A threshold tick is visible. Below-threshold values are amber. |

## F. Process (for the team, not the screen)

| ID | Law | Rule |
|---|---|---|
| F1 | Pareto Principle | Build the six MVP console items (UI_WORKFLOW §1) before anything else. |
| F2 | Parkinson's Law | Every step has a time box (see AGENT_WORKFLOW). When it runs out, ship what works and log the rest. |
| F3 | Occam's Razor | Choose the simplest component that passes the check. No state library, no animation library unless a rule needs one. |

## Severity for review findings

- **Blocker:** an MVP item is missing or wrong, it breaks at demo time (crash, blank screen), or it violates B1, C5, D3 or A3.
- **Major:** any other failed **Check** on the main console.
- **Minor:** polish, or anything on stretch screens.

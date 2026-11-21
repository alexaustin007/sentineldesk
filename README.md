# sentineldesk
SentinelDesk Hackathon project for multilingual incident triage and evidence-backed resolution drafts

## Hackathon dataset

Use the organizer-recommended 20K CSV for development and evaluation. The dataset is published by Tobi-Bueck under CC BY-NC 4.0. [Download the CSV](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/dataset-tickets-multi-lang-4-20k.csv) · [Hugging Face dataset card](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets)

From the repository root, download a local copy.

```bash
mkdir -p data
curl --fail --location --silent --show-error \
  --output data/dataset-tickets-multi-lang-4-20k.csv \
  https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/main/dataset-tickets-multi-lang-4-20k.csv
```

Keep the downloaded CSV local and commit code and instructions to GitHub.

- Use the optional `subject` and the `body` as ticket inputs. Tickets include English and German.
- Use a reproducible 80/20 split (seed 42 in the brief). Train on the historical 80% with `type`, `queue`, and `priority` as labels. Index `answer` only for historical rows.
- Pass only the subject and body to the app during holdout evaluation. Use holdout labels only for scoring, and keep holdout answers out of training, the retrieval index, and model prompts.

[Organizer’s brief and evaluation rules](https://docs.google.com/document/u/0/d/1KeZWHjmfjx00pQIGDGHroOCecdvJzpkU/mobilebasic?pli=1)

## Triage workflow (RAG and agents)

The `sentineldesk` package holds the retrieval engine and the agent workflow. Each ticket goes through these steps:

1. **Guardrails.** The workflow detects the language (only English and German get automated replies), masks personal data, and screens for prompt injection.
2. **Agent 1: classifier.** The team's trained model plugs in through `TicketClassifier`.
3. **Agent 2: precedent vote.** FAISS retrieves similar historical tickets, and they vote on type, queue, and priority, weighted by similarity.
4. **Mandatory escalation.** Any high-priority Incident goes straight to the on-call engineer, with no LLM call.
5. **Routing.** When both agents agree with enough confidence, the evidence is strong, and there are no risk cues, Gemini Flash-Lite drafts the reply. Otherwise Gemini Flash first challenges the triage as an adversarial reviewer.
6. **Verification.** Every draft must cite retrieved tickets. Unsupported promises such as amounts, deadlines, refunds, or guarantees are removed, and any removal or security finding sends the draft to human review.

### Run it

```bash
python -m pip install -r requirements.txt
```

```bash
python -m pytest
```

```bash
python -m sentineldesk.demo
```

Without a Gemini key, everything runs offline with a mock LLM. The demo uses TF-IDF retrieval on the mock tickets unless `SENTINEL_EMBEDDER=sentence-transformers` is set. The multilingual model downloads (about 470 MB) on first use.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | not set | Turns on Gemini. Without it the mock LLM runs. |
| `SENTINEL_LLM_PROVIDER` | `auto` | Set to `gemini` or `mock` to force one. |
| `SENTINEL_FAST_MODEL` | `gemini-3.5-flash-lite` | Routine drafts |
| `SENTINEL_DEEP_MODEL` | `gemini-3.8-flash` | Adversarial review, complex drafts, attachments |
| `SENTINEL_FAST_INPUT_PRICE`, `SENTINEL_FAST_OUTPUT_PRICE` | `0.30`, `2.50` | USD per million tokens, used for cost estimates |
| `SENTINEL_DEEP_INPUT_PRICE`, `SENTINEL_DEEP_OUTPUT_PRICE` | `0.75`, `3.75` | USD per million tokens, used for cost estimates |
| `SENTINEL_EMBEDDER` | `sentence-transformers` | Set to `tfidf` for offline retrieval |
| `SENTINEL_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Multilingual retrieval model |

Keep API keys in your shell or an untracked `.env` file. Tune the thresholds in `TriageConfig` on a validation slice of the historical split, never on the holdout.

### Integration points

- **Data:** `load_historical_tickets()` in `sentineldesk/data_interface.py` returns mock tickets for now. Return the official historical split there. Pass the holdout ticket IDs to `PrecedentIndex.build(..., holdout_ticket_ids=...)` so the build fails if any holdout ticket gets indexed.
- **Classifier:** Implement `predict(subject, body) -> TicketLabels`, or wrap three fitted scikit-learn models with `SklearnClassifierAdapter({"type": ..., "queue": ..., "priority": ...})`.
- **UI:** Build one `TriageOrchestrator` and cache it, then call `triage(subject, body)` for each ticket. The returned `TriageResult` has the status, reasons, labels with confidence, precedents, draft, latency, tokens, and cost. `result.to_dict()` gives plain JSON.

## Contributing

Read [AGENTS.md](AGENTS.md) before editing. If you use a coding agent, point it to that file when you start work. The guide covers Python style, how to organize code, and the rules for working with the dataset.

### Start from a branch

Every change to `main` goes through a pull request, including changes from the repository owner.

```bash
git fetch origin
git switch -c fix/ticket-validation origin/main
```

Use your own short, descriptive branch name. If you are working from a fork, fetch the latest `main` from the upstream SentinelDesk repository and branch from there.

### Verify and open a pull request

Install Ruff in your development environment and run these commands from the repository root.

```bash
python -m pip install ruff==0.17.6
ruff format .
ruff check .
ruff format --check .
```

Ruff uses four spaces per indentation level. Commit your changes, push your branch to the repository or your fork, and open a pull request against SentinelDesk’s `main`. Include a brief summary and explain how you verified the change. Merge through the pull request once **Ruff lint and format** passes. The **Python quality** workflow also checks pushes to `main`.

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

### Prepare the local split

After downloading the CSV, run the preparation script with Python 3.10 or later. It uses the Python standard library.

```bash
python3 scripts/prepare_data.py
```

The script assigns IDs from the original one-based CSV record number, trims surrounding whitespace, keeps blank subjects, and skips tickets with a blank body. It preserves label spelling and case. A seed-42 shuffle puts 80% of usable tickets (rounded down) into the historical split and reserves the rest for evaluation. Run the command again with the same source to reproduce the files in `data/prepared/`.

| Local file | Columns | Use |
| --- | --- | --- |
| `train.csv` | ticket_id, subject, body, type, queue, priority, language | Train classifiers on subject and body using the historical labels. |
| `knowledge_base.csv` | ticket_id, subject, body, answer, language | Index historical tickets with a nonblank resolution. Cite their IDs in drafts. |
| `holdout_inputs.csv` | ticket_id, subject, body | Pass only subject and body to the app. Keep the ID to match predictions to labels. |
| `holdout_labels.csv` | ticket_id, type, queue, priority, language | Join by ID in the scoring script after inference. |

Use a validation subset of the historical split when tuning models or thresholds. Reserve the holdout for final scoring. Git ignores the local data directory and CSV files.

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

After [preparing the local split](#prepare-the-local-split), embed the historical tickets once and save the index to `artifacts/precedent_index` (git ignores it). The multilingual model downloads, about 470 MB, on first use.

```bash
python -m sentineldesk.build_index
```

Check how well the precedent vote predicts labels on a validation slice of the historical split. It uses no holdout data.

```bash
python -m sentineldesk.rag_validation
```

Run the demo on sample tickets:

```bash
python -m sentineldesk.demo
```

Without the prepared split, the demo falls back to 16 mock tickets with offline TF-IDF retrieval. Without a Gemini key, it uses a mock LLM.

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

- **Data:** `load_historical_tickets()` in `sentineldesk/data_interface.py` reads `data/prepared/`. It joins the answers in `knowledge_base.csv` with the labels in `train.csv` by ticket ID, and refuses to continue if any ID from `holdout_inputs.csv` would be indexed.
- **Classifier:** Implement `predict(subject, body) -> TicketLabels`, or wrap three fitted scikit-learn models with `SklearnClassifierAdapter({"type": ..., "queue": ..., "priority": ...})`. The adapter sends `{"subject", "body"}` records, matching `make_ticket_features()`.
- **UI:** Call `create_orchestrator(classifier=...)` from `sentineldesk.app_factory` once and cache it, for example with `st.cache_resource`. Then call `triage(subject, body)` for each ticket. The returned `TriageResult` has the status, reasons, labels with confidence, precedents, draft, latency, tokens, and cost. `result.to_dict()` gives plain JSON.

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

## TF-IDF features for classification

Start with the local `data/prepared/train.csv` from [data preparation](https://github.com/alexaustin007/sentineldesk/pull/2). Install the dependency with `python -m pip install -r requirements.txt`. From the repository root:

```python
import csv

from ticket_features import make_ticket_features

with open("data/prepared/train.csv", encoding="utf-8", newline="") as stream:
    training = list(csv.DictReader(stream))

features = make_ticket_features()
X_train = features.fit_transform(training)
priorities = [row["priority"] for row in training]  # Same row order as X_train
X_new = features.transform([{"body": "Mein VPN funktioniert nicht."}])
```

The pipeline combines the optional subject with the body and returns a sparse matrix of word and two-word phrase weights. Reuse the same matrix with the type, queue, and priority labels. For validation, split the historical rows first and fit on the training portion only. Use `transform()` for validation, holdout inputs, and live tickets. For cross-validation, put this unfitted pipeline before the classifier in a scikit-learn pipeline so each fold learns its own vocabulary.

Save the fitted pipeline locally alongside the matching classifiers (for example, `joblib.dump(features, "data/prepared/ticket_features.joblib")` after importing `joblib`). Load that same pipeline for inference.

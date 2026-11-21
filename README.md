# sentineldesk
SentinelDesk Hackathon project for multilingual incident triage and evidence-backed resolution drafts

## Hackathon dataset

The team uses the full three-file snapshot of Tobi-Bueck's Customer Support Tickets dataset (CC BY-NC 4.0). Download all three CSVs from the pinned revision and prepare them with Python 3.10 or later. [Dataset card](https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets)

```bash
mkdir -p data
source_url=https://huggingface.co/datasets/Tobi-Bueck/customer-support-tickets/resolve/ddf1c81a5475992c4fa6752bf1e8b4e31f07bbeb
for file in dataset-tickets-multi-lang-4-20k.csv aa_dataset-tickets-multi-lang-5-2-50-version.csv dataset-tickets-german_normalized_50_5_2.csv; do
    curl --fail --location --silent --show-error --retry 2 "$source_url/$file" --output "data/$file" || break
done
```

### Prepare the local split

```bash
python3 scripts/prepare_data.py --dataset full
```

Of 61,765 source records, 48,587 have type, queue, priority, and language. The other 13,178 have queue and priority only and lack resolutions. Preparation skips two blank bodies and collapses 8,309 repeated subject/body pairs to produce 40,276 distinct labeled inputs. Matching ignores case and whitespace. When copies differ, the first 20K record takes precedence, followed by file order in the newer labeled CSV. A duplicate can supply a missing answer. Blank subjects are supported.

The seed-42 split keeps identical normalized bodies together, even across different subjects. Existing 20K training bodies stay in training. Existing holdout bodies stay in evaluation unless also present in the old training set. New body groups fill the remaining holdout allocation. Original 20K IDs stay stable; additional tickets use `TKT-V5-` plus the one-based source record number.

The pinned snapshot yields **32,220 training tickets**, **32,214 historical resolutions**, and **8,056 held-out tickets**. Use the same preparation mode across the team and rebuild TF-IDF, classifiers, and the retrieval index when switching. To reproduce the prototype, download the 20K CSV and run `python3 scripts/prepare_data.py --dataset 20k`. Both modes write the same four files to `data/prepared/`.

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

Score the whole workflow on the holdout split and write the Metrics page report (`ui/public/metrics.json`, not committed). It covers the classifier blended with the precedent vote, the escalation gate, and a live Gemini sample: it labels every holdout ticket without LLM calls, then runs 30 sampled tickets through live Gemini for latency, cost, and draft checks. Holdout labels are read only after all predictions are made. For the classifier-only benchmark, use `python -m scripts.evaluate_holdout` instead (see below). Both write the same file, so publish one per release.

```bash
python -m sentineldesk.evaluate_holdout
```

Run the demo on sample tickets:

```bash
python -m sentineldesk.demo
```

Without the prepared split, the demo falls back to 16 mock tickets with offline TF-IDF retrieval. It uses the trained classifier from `python classification/classify.py` when its models exist, and a keyword mock otherwise. Without Gemini credentials, it uses a mock LLM.

To run Gemini on Google Cloud credits, sign in once with Application Default Credentials and set the Google Cloud variables listed below:

```bash
gcloud auth application-default login
```

Then confirm that both model tiers answer:

```bash
python -m sentineldesk.check_llm
```

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_GENAI_USE_ENTERPRISE` | not set | Set to `true` to run Gemini on Google Cloud (Vertex AI / Gemini Enterprise Agent Platform) with Application Default Credentials, for Google Cloud credits. |
| `GOOGLE_CLOUD_PROJECT` | not set | Google Cloud project ID, required in Google Cloud mode |
| `GOOGLE_CLOUD_LOCATION` | `global` | Google Cloud location for Gemini |
| `GEMINI_API_KEY` | not set | Gemini Developer API key from Google AI Studio. Without any Gemini credentials the mock LLM runs. |
| `SENTINEL_LLM_PROVIDER` | `auto` | Set to `enterprise`, `gemini`, or `mock` to force one. |
| `SENTINEL_FAST_MODEL` | `gemini-3.5-flash-lite` | Routine drafts |
| `SENTINEL_DEEP_MODEL` | `gemini-3.8-flash` | Adversarial review, complex drafts, attachments |
| `SENTINEL_FAST_INPUT_PRICE`, `SENTINEL_FAST_OUTPUT_PRICE` | `0.30`, `2.50` | USD per million tokens, used for cost estimates |
| `SENTINEL_DEEP_INPUT_PRICE`, `SENTINEL_DEEP_OUTPUT_PRICE` | `0.75`, `3.75` | USD per million tokens, used for cost estimates |
| `SENTINEL_EMBEDDER` | `sentence-transformers` | Set to `tfidf` for offline retrieval |
| `SENTINEL_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Multilingual retrieval model |

Keep API keys in your shell or an untracked `.env` file. Tune the thresholds in `TriageConfig` on a validation slice of the historical split, never on the holdout.

### Run the console against the real backend

Start the API on port 8000. The console's dev server forwards `/api` to it.

```bash
.venv/bin/uvicorn api.main:app --port 8000
```

Point the console at the live API instead of its mock data, then start it on port 5173:

```bash
printf 'VITE_USE_MOCK=false\n' > ui/.env.development.local
```

```bash
npm --prefix ui install && npm --prefix ui run dev
```

**Hosting (for example Vercel):** the API cannot run as a Vercel function, because the embedding model, index, and classifier are far larger than Vercel's function size limit. Run the API on a machine or service Vercel can reach, then either rewrite `/api/*` to it in Vercel, or call it directly and list the console's origin in `SENTINEL_ALLOWED_ORIGINS` (comma-separated).

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

Start with the local `data/prepared/train.csv` from the [local split](#prepare-the-local-split). Install the dependency with `python -m pip install -r requirements.txt`. From the repository root:

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

### Publish the classifier holdout benchmark

From the repo root, run `python -m scripts.evaluate_holdout` after preparing the full split. It fits the team's classifier on the historical training set, predicts from holdout subject and body, then joins the hidden labels by ticket ID to score predictions. The generated `ui/public/metrics.json` contains only aggregate counts and scores. Build the frontend after generating the report so Vite includes it.

For the Vercel demo, build with `VITE_USE_MOCK=false` and deploy the contents of `ui/dist/` with the rewrites in `ui/vercel.json`. The backend laptop and its tunnel must stay online. The Metrics page shows the last successful live decision in the current tab. Its classifier benchmark updates when a new evaluation report is published.

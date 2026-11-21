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

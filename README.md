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

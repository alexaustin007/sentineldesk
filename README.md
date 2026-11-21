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

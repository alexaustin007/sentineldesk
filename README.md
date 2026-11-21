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

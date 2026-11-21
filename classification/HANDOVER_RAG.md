# Classification System Handover for RAG Pipeline

**Author:** Ivy Chepkwony
**Date:** 2026-11-21
**Status:** MVP ready for integration. Calibration, ensemble, and critical incident classifier still in progress.

---

## Quick start

```python
from classification.classify import classify_ticket, load_models

# Load once at app startup (loads 3 saved SVM pipelines from disk)
pipelines = load_models()

# Classify a ticket
result = classify_ticket(
    subject="VPN not connecting",
    body="I cannot connect to the corporate VPN since this morning.",
    pipelines=pipelines,
)
```

**Prerequisites:**
- Run `pip install -r requirements.txt` (needs scikit-learn, pandas, langdetect, joblib)
- Trained models must exist in `classification/models/`. To train them: `python classification/classify.py`

---

## Output schema

`classify_ticket()` returns a dict matching the Section 9.2 contract from classification_plan.md:

```json
{
    "predicted_type": "Incident",
    "predicted_queue": "Technical Support",
    "predicted_priority": "high",
    "confidence": {
        "type": 0.91,
        "queue": 0.37,
        "priority": 0.41
    },
    "classification_margin": {
        "type": 0.85,
        "queue": 0.16,
        "priority": 0.11
    },
    "escalation": {
        "required": true,
        "reasons": ["Low confidence on queue (0.37)", "Narrow margin on priority (0.11)"]
    },
    "detected_language": "en",
    "inference_latency_ms": 320.3
}
```

## Fields the RAG pipeline needs

| Field | Type | Use |
|-------|------|-----|
| `predicted_type` | str | One of: Incident, Request, Problem, Change |
| `predicted_queue` | str | One of 10 queues (Technical Support, Product Support, etc.) |
| `predicted_priority` | str | One of: high, medium, low |
| `detected_language` | str | "en" or "de" — auto-detected from body text |
| `escalation.required` | bool | If true, do not auto-generate a reply; route to human |
| `confidence` | dict[str, float] | Per-target confidence scores (0.0-1.0) |

The RAG system should use `predicted_type`, `predicted_queue`, and `detected_language` to filter or weight historical ticket retrieval. Use `escalation.required` to decide whether to generate a draft reply at all.

---

## Current model performance (validation set, n=4833)

| Target | Model | Macro-F1 | Notes |
|--------|-------|----------|-------|
| Type | SVM | 0.837 | Strong. Problem class weakest (0.59 F1) |
| Queue | SVM | 0.541 | Below target. Minority queues (HR, Sales, General Inquiry) weak |
| Priority | SVM | 0.548 | Below target. Low-priority recall only 31% |

**What this means for RAG:** Type predictions are reliable. Queue and priority predictions are directional but noisy — the RAG pipeline should not hard-filter on queue/priority alone. Use them as soft weights for retrieval ranking rather than strict filters.

---

## What is still changing

These improvements are in progress and may change confidence scores and escalation behavior, but the output schema and function signature are stable:

- Calibration of probability estimates
- Dedicated critical incident binary classifier (adds `critical_incident_risk` field)
- Class weighting experiments for queue/priority
- Ensemble evaluation (may swap SVM for a model combination)
- Escalation threshold tuning

The `classify_ticket()` interface will not break. New fields may be added to the output dict.

---

## Batch predictions (for development and testing)

To generate predictions for the entire holdout set:

```bash
python classification/predict.py
```

This writes `data/prepared/holdout_predictions.json` — an array of prediction objects, one per holdout ticket, each with a `ticket_id` you can join against `holdout_inputs.csv`.

**Files the RAG team should use:**

| File | What it is | How to use it |
|------|-----------|---------------|
| `data/prepared/holdout_predictions.json` | Classifications for every holdout ticket | Load and join by `ticket_id` with holdout inputs to test retrieval |
| `data/prepared/knowledge_base.csv` | Historical tickets with answers | Build the retrieval index from these |
| `data/prepared/holdout_inputs.csv` | Raw holdout tickets (subject + body only) | The tickets your RAG system will draft replies for |

Example — loading predictions and joining with inputs:

```python
import json
import pandas as pd

with open("data/prepared/holdout_predictions.json") as f:
    preds = json.load(f)

preds_df = pd.DataFrame(preds)
inputs_df = pd.read_csv("data/prepared/holdout_inputs.csv")

# Join predictions with ticket text
tickets = inputs_df.merge(preds_df, on="ticket_id")
# tickets now has: ticket_id, subject, body, predicted_type, predicted_queue, etc.
```

---

## File layout

```
classification/
    classify.py      # Inference: classify_ticket(), load_models(), train_and_save()
    predict.py       # Batch predictions: runs models on holdout_inputs.csv -> JSON
    train.py         # Benchmarking script (LR, SVM, CNB comparisons)
    models/          # Saved joblib pipelines (gitignored, generated by classify.py)
        svm_type.joblib
        svm_queue.joblib
        svm_priority.joblib
    HANDOVER_RAG.md  # This document
ticket_features.py   # Shared TF-IDF pipeline (used by both training and inference)
data/prepared/
    holdout_predictions.json  # Generated by predict.py (gitignored)
    knowledge_base.csv        # Historical tickets with answers for RAG indexing
    holdout_inputs.csv        # Raw holdout tickets for inference
```

"""Build a classifier benchmark. Run as python -m scripts.evaluate_holdout."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

from classification.classify import TARGETS, _make_svm_pipeline


def evaluate(prepared: Path) -> dict:
    train = pd.read_csv(prepared / "train.csv", keep_default_na=False)
    inputs = pd.read_csv(prepared / "holdout_inputs.csv", keep_default_na=False)
    for frame in (train, inputs):
        frame.set_index("ticket_id", verify_integrity=True, inplace=True)
    if not train.index.intersection(inputs.index).empty:
        raise ValueError("Train and holdout IDs overlap")
    if set(train.body.str.strip().str.casefold()) & set(
        inputs.body.str.strip().str.casefold()
    ):
        raise ValueError("Train and holdout bodies overlap")

    train_text = train[["subject", "body"]].to_dict("records")
    test_text = inputs[["subject", "body"]].to_dict("records")
    predictions = pd.DataFrame(index=inputs.index)
    np.random.seed(42)
    for target in TARGETS:
        print(f"Fitting and scoring {target}", flush=True)
        model = _make_svm_pipeline().fit(train_text, train[target])
        probabilities = model.predict_proba(test_text)
        predictions[target] = model.classes_[probabilities.argmax(axis=1)]

    truth = pd.read_csv(prepared / "holdout_labels.csv").set_index(
        "ticket_id", verify_integrity=True
    )
    if (
        set(truth.index) != set(predictions.index)
        or truth[list(TARGETS)].isna().any().any()
    ):
        raise ValueError(
            "Each holdout prediction needs exactly one complete set of labels"
        )
    truth = truth.loc[predictions.index]
    heads = {}
    for target in TARGETS:
        labels = sorted(set(truth[target]) | set(predictions[target]))
        report = classification_report(
            truth[target],
            predictions[target],
            labels=labels,
            output_dict=True,
            zero_division=0,
        )
        heads[target] = {
            "labels": labels,
            "accuracy": float((predictions[target] == truth[target]).mean()),
            "macro_f1": report["macro avg"]["f1-score"],
            "confusion": confusion_matrix(
                truth[target], predictions[target], labels=labels
            ).tolist(),
            "per_class": [
                {
                    "label": label,
                    "precision": report[label]["precision"],
                    "recall": report[label]["recall"],
                    "f1": report[label]["f1-score"],
                    "support": int(report[label]["support"]),
                }
                for label in labels
            ],
        }
    urgent = (truth.type == "Incident") & (truth.priority == "high")
    flagged = (predictions.type == "Incident") & (predictions.priority == "high")
    total, caught = int(urgent.sum()), int((urgent & flagged).sum())
    if not total:
        raise ValueError(
            "Cannot score urgent incident recall without labeled urgent incidents"
        )
    return {
        "evaluation_scope": "classifier",
        "sample": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": "TF-IDF + calibrated LinearSVC",
        "heads": heads,
        "split": {"train": len(train), "holdout": len(inputs)},
        "high_priority_incident_recall": caught / total,
        "high_priority_incident": {"caught": caught, "total": total},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, default=Path("data/prepared"))
    parser.add_argument("--output", type=Path, default=Path("ui/public/metrics.json"))
    args = parser.parse_args()
    report = evaluate(args.prepared)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Wrote {args.output} for {report['split']['holdout']} holdout tickets")


if __name__ == "__main__":
    main()

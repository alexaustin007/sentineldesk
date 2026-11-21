"""Model diversity analysis (Section 5.2 of classification plan).

Measures whether SVM, LR, and CNB make different enough errors to justify
an ensemble. Computes disagreement rate, error correlation, and conditional
accuracy for each pair of models on each target.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ticket_features import make_ticket_features

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIN_CSV = PROJECT_ROOT / "data" / "prepared" / "train.csv"
TARGETS = ("type", "queue", "priority")
RANDOM_STATE = 42
VAL_SIZE = 0.15


def to_dicts(df: pd.DataFrame) -> list[dict[str, str]]:
    return df[["subject", "body"]].to_dict(orient="records")


def make_pipeline(model_name: str, class_weight: str | None = None) -> Pipeline:
    features = make_ticket_features()
    if model_name == "svm":
        features.steps.append(
            (
                "clf",
                CalibratedClassifierCV(
                    LinearSVC(max_iter=10_000, class_weight=class_weight), cv=5
                ),
            )
        )
    elif model_name == "lr":
        features.steps.append(
            (
                "clf",
                LogisticRegression(
                    max_iter=1000, solver="saga", class_weight=class_weight
                ),
            )
        )
    elif model_name == "cnb":
        features.steps.append(("clf", ComplementNB(alpha=1.0)))
    return features


def diversity_metrics(
    preds_a: np.ndarray,
    preds_b: np.ndarray,
    y_true: np.ndarray,
) -> dict:
    """Compute pairwise diversity metrics between two models."""
    n = len(y_true)
    disagree = (preds_a != preds_b).sum()
    disagree_rate = disagree / n

    errors_a = preds_a != y_true
    errors_b = preds_b != y_true

    # Error correlation: how often both are wrong at the same time
    both_wrong = (errors_a & errors_b).sum()
    either_wrong = (errors_a | errors_b).sum()
    error_overlap = both_wrong / either_wrong if either_wrong > 0 else 0.0

    # Conditional accuracy: when A is wrong, how often is B right?
    a_wrong = errors_a.sum()
    b_right_when_a_wrong = (errors_a & ~errors_b).sum()
    cond_acc_b_given_a_wrong = b_right_when_a_wrong / a_wrong if a_wrong > 0 else 0.0

    b_wrong = errors_b.sum()
    a_right_when_b_wrong = (errors_b & ~errors_a).sum()
    cond_acc_a_given_b_wrong = a_right_when_b_wrong / b_wrong if b_wrong > 0 else 0.0

    return {
        "disagreement_rate": round(disagree_rate, 4),
        "error_overlap": round(error_overlap, 4),
        "cond_acc_b|a_wrong": round(cond_acc_b_given_a_wrong, 4),
        "cond_acc_a|b_wrong": round(cond_acc_a_given_b_wrong, 4),
    }


def main():
    df = pd.read_csv(TRAIN_CSV)
    df["subject"] = df["subject"].fillna("")

    dev_df, val_df = train_test_split(
        df, test_size=VAL_SIZE, random_state=RANDOM_STATE, stratify=df["type"]
    )

    X_dev = to_dicts(dev_df)
    X_val = to_dicts(val_df)

    model_names = ["svm", "lr", "cnb"]

    for target in TARGETS:
        weight = "balanced" if target in ("queue", "priority") else None
        print(f"\n{'=' * 60}")
        print(
            f"TARGET: {target.upper()}"
            + (f" (class_weight={weight})" if weight else "")
        )
        print("=" * 60)

        y_dev = dev_df[target].values
        y_val = val_df[target].values

        predictions: dict[str, np.ndarray] = {}
        f1s: dict[str, float] = {}

        for name in model_names:
            cw = weight if name != "cnb" else None  # CNB doesn't support class_weight
            pipe = make_pipeline(name, class_weight=cw)
            pipe.fit(X_dev, y_dev)
            preds = pipe.predict(X_val)
            predictions[name] = preds
            f1s[name] = round(f1_score(y_val, preds, average="macro"), 4)

        print(f"\nIndividual Macro-F1: {f1s}")

        # Pairwise diversity
        pairs = [("svm", "lr"), ("svm", "cnb"), ("lr", "cnb")]
        print(
            f"\n{'Pair':<12} {'Disagree%':>10} {'ErrorOverlap':>13} {'B_right|A_wrong':>16} {'A_right|B_wrong':>16}"
        )
        print("-" * 70)
        for a, b in pairs:
            metrics = diversity_metrics(predictions[a], predictions[b], y_val)
            print(
                f"{a}–{b:<8} {metrics['disagreement_rate']:>10.1%} "
                f"{metrics['error_overlap']:>13.1%} "
                f"{metrics['cond_acc_b|a_wrong']:>16.1%} "
                f"{metrics['cond_acc_a|b_wrong']:>16.1%}"
            )

        # Quick ensemble check: majority vote
        all_preds = np.column_stack([predictions[n] for n in model_names])
        majority = np.array([pd.Series(row).mode()[0] for row in all_preds])
        majority_f1 = round(f1_score(y_val, majority, average="macro"), 4)
        best_single = max(f1s.values())
        delta = round(majority_f1 - best_single, 4)
        print(
            f"\nMajority vote Macro-F1: {majority_f1} (best single: {best_single}, delta: {delta:+.4f})"
        )
        if delta > 0:
            print("  -> Ensemble HELPS")
        else:
            print("  -> Ensemble does NOT help (best single model is better)")


if __name__ == "__main__":
    main()

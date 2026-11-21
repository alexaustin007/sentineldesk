"""Full evaluation pipeline for SentinelDesk classification.

Produces:
1. Confusion matrices for each target (type, queue, priority) on validation set
2. Critical incident binary classifier (Section 3.2 of the plan)
3. Holdout evaluation (final metrics on unseen data)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from langdetect import LangDetectException, detect
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ticket_features import make_ticket_features

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "prepared"
TRAIN_CSV = DATA_DIR / "train.csv"
HOLDOUT_INPUTS = DATA_DIR / "holdout_inputs.csv"
HOLDOUT_LABELS = DATA_DIR / "holdout_labels.csv"

TARGETS = ("type", "queue", "priority")
RANDOM_STATE = 42
VAL_SIZE = 0.15


TARGET_WEIGHTS: dict[str, str | None] = {
    "type": None,
    "queue": "balanced",
    "priority": "balanced",
}


def _make_svm_pipeline(class_weight: str | None = None) -> Pipeline:
    features = make_ticket_features()
    features.steps.append(
        (
            "clf",
            CalibratedClassifierCV(
                LinearSVC(max_iter=10_000, class_weight=class_weight), cv=5
            ),
        )
    )
    return features


def to_dicts(df: pd.DataFrame) -> list[dict[str, str]]:
    return df[["subject", "body"]].to_dict(orient="records")


def print_confusion_matrix(y_true: pd.Series, y_pred: np.ndarray, labels: list):
    """Print a labeled confusion matrix."""
    str_labels = [str(l) for l in labels]
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    max_label = max(len(s) for s in str_labels)
    header = " " * (max_label + 2) + "  ".join(f"{s[:8]:>8}" for s in str_labels)
    print(header)
    for i, label in enumerate(str_labels):
        row = "  ".join(f"{cm[i, j]:>8}" for j in range(len(labels)))
        print(f"{label:>{max_label}}  {row}")
    print()

    for i, label in enumerate(str_labels):
        fp = cm[:, i].sum() - cm[i, i]
        fn = cm[i, :].sum() - cm[i, i]
        tp = cm[i, i]
        print(f"  {label}: TP={tp}, FP={fp}, FN={fn}")
    print()


# -----------------------------------------------------------------------
# 1. Validation-set evaluation with confusion matrices
# -----------------------------------------------------------------------
def evaluate_validation():
    print("=" * 70)
    print("PART 1: VALIDATION SET — CONFUSION MATRICES")
    print("=" * 70)

    df = pd.read_csv(TRAIN_CSV)
    df["subject"] = df["subject"].fillna("")

    dev_df, val_df = train_test_split(
        df, test_size=VAL_SIZE, random_state=RANDOM_STATE, stratify=df["type"]
    )
    print(f"Dev: {len(dev_df)} | Val: {len(val_df)}\n")

    X_dev = to_dicts(dev_df)
    X_val = to_dicts(val_df)

    val_pipelines: dict[str, Pipeline] = {}

    for target in TARGETS:
        pipe = _make_svm_pipeline(class_weight=TARGET_WEIGHTS[target])
        pipe.fit(X_dev, dev_df[target])
        y_pred = pipe.predict(X_val)
        labels = sorted(val_df[target].unique())

        macro_f1 = f1_score(val_df[target], y_pred, average="macro")
        print(f"\n--- {target.upper()} (Macro-F1: {macro_f1:.4f}) ---")
        print(classification_report(val_df[target], y_pred, zero_division=0))
        print("Confusion matrix (rows=actual, cols=predicted):")
        print_confusion_matrix(val_df[target], y_pred, labels)

        val_pipelines[target] = pipe

    return dev_df, val_df, val_pipelines


# -----------------------------------------------------------------------
# 2. Critical incident binary classifier (Section 3.2)
# -----------------------------------------------------------------------
def evaluate_critical_incident(dev_df: pd.DataFrame, val_df: pd.DataFrame):
    print("=" * 70)
    print("PART 2: CRITICAL INCIDENT BINARY CLASSIFIER")
    print("=" * 70)

    dev_df = dev_df.copy()
    val_df = val_df.copy()
    dev_df["critical"] = (
        (dev_df["type"] == "Incident") & (dev_df["priority"] == "high")
    ).astype(int)
    val_df["critical"] = (
        (val_df["type"] == "Incident") & (val_df["priority"] == "high")
    ).astype(int)

    print(f"\nCritical incidents in dev:  {dev_df['critical'].sum()} / {len(dev_df)}")
    print(f"Critical incidents in val:  {val_df['critical'].sum()} / {len(val_df)}")

    X_dev = to_dicts(dev_df)
    X_val = to_dicts(val_df)

    pipe = _make_svm_pipeline()
    pipe.fit(X_dev, dev_df["critical"])

    y_pred = pipe.predict(X_val)
    y_proba = pipe.predict_proba(X_val)[:, 1]

    print("\nBinary classification report:")
    print(
        classification_report(
            val_df["critical"], y_pred, target_names=["not critical", "critical"]
        )
    )

    print("Confusion matrix (rows=actual, cols=predicted):")
    print_confusion_matrix(val_df["critical"], y_pred, [0, 1])

    print("Recall at various thresholds:")
    print(f"{'Threshold':>10} {'Recall':>8} {'Precision':>10} {'Escalation%':>12}")
    print("-" * 44)
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        preds_at_thresh = (y_proba >= threshold).astype(int)
        rec = recall_score(val_df["critical"], preds_at_thresh, zero_division=0)
        prec = precision_score(val_df["critical"], preds_at_thresh, zero_division=0)
        escalation_rate = preds_at_thresh.mean() * 100
        print(f"{threshold:>10.1f} {rec:>8.3f} {prec:>10.3f} {escalation_rate:>11.1f}%")
    print()

    return pipe


# -----------------------------------------------------------------------
# 3. Holdout evaluation (Section 10.1 — one-time final metrics)
# -----------------------------------------------------------------------
def evaluate_holdout():
    print("=" * 70)
    print("PART 3: HOLDOUT EVALUATION (FINAL)")
    print("=" * 70)

    train_df = pd.read_csv(TRAIN_CSV)
    train_df["subject"] = train_df["subject"].fillna("")
    holdout_inputs = pd.read_csv(HOLDOUT_INPUTS)
    holdout_inputs["subject"] = holdout_inputs["subject"].fillna("")
    holdout_labels = pd.read_csv(HOLDOUT_LABELS)

    X_train = to_dicts(train_df)
    X_holdout = to_dicts(holdout_inputs)

    print(f"\nTraining on full train set: {len(train_df)} tickets")
    print(f"Evaluating on holdout: {len(holdout_labels)} tickets\n")

    for target in TARGETS:
        pipe = _make_svm_pipeline(class_weight=TARGET_WEIGHTS[target])
        pipe.fit(X_train, train_df[target])
        y_pred = pipe.predict(X_holdout)
        labels = sorted(holdout_labels[target].unique())

        macro_f1 = f1_score(holdout_labels[target], y_pred, average="macro")
        weighted_f1 = f1_score(holdout_labels[target], y_pred, average="weighted")

        print(
            f"\n--- {target.upper()} (Macro-F1: {macro_f1:.4f} | Weighted-F1: {weighted_f1:.4f}) ---"
        )
        print(classification_report(holdout_labels[target], y_pred, zero_division=0))
        print("Confusion matrix (rows=actual, cols=predicted):")
        print_confusion_matrix(holdout_labels[target], y_pred, labels)

    # Critical incident on holdout
    print("\n--- CRITICAL INCIDENT (holdout) ---")
    train_df_c = train_df.copy()
    train_df_c["critical"] = (
        (train_df_c["type"] == "Incident") & (train_df_c["priority"] == "high")
    ).astype(int)
    holdout_labels["critical"] = (
        (holdout_labels["type"] == "Incident") & (holdout_labels["priority"] == "high")
    ).astype(int)

    pipe = _make_svm_pipeline()
    pipe.fit(X_train, train_df_c["critical"])
    y_pred = pipe.predict(X_holdout)
    y_proba = pipe.predict_proba(X_holdout)[:, 1]

    print(
        classification_report(
            holdout_labels["critical"],
            y_pred,
            target_names=["not critical", "critical"],
        )
    )

    print("Holdout — recall at thresholds:")
    print(f"{'Threshold':>10} {'Recall':>8} {'Precision':>10} {'Escalation%':>12}")
    print("-" * 44)
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        preds_at_thresh = (y_proba >= threshold).astype(int)
        rec = recall_score(holdout_labels["critical"], preds_at_thresh, zero_division=0)
        prec = precision_score(
            holdout_labels["critical"], preds_at_thresh, zero_division=0
        )
        escalation_rate = preds_at_thresh.mean() * 100
        print(f"{threshold:>10.1f} {rec:>8.3f} {prec:>10.3f} {escalation_rate:>11.1f}%")


# -----------------------------------------------------------------------
# 4. Language-specific evaluation (Section 10.3)
# -----------------------------------------------------------------------
def _detect_lang(text: str) -> str:
    try:
        lang = detect(text)
        return "de" if lang == "de" else "en"
    except LangDetectException:
        return "en"


def evaluate_by_language(df: pd.DataFrame, y_preds: dict[str, np.ndarray]):
    """Report Macro-F1 split by detected language for each target."""
    print("=" * 70)
    print("PART 4: LANGUAGE-SPECIFIC EVALUATION")
    print("=" * 70)

    texts = [
        f"{(row.get('subject') or '').strip()}\n{row['body'].strip()}"
        for _, row in df.iterrows()
    ]
    langs = pd.Series([_detect_lang(t) for t in texts], index=df.index)

    lang_counts = langs.value_counts()
    print(f"\nLanguage distribution: {dict(lang_counts)}\n")

    for target, y_pred in y_preds.items():
        print(f"--- {target.upper()} by language ---")
        for lang in sorted(langs.unique()):
            mask = langs == lang
            if mask.sum() == 0:
                continue
            mf1 = f1_score(df.loc[mask, target], y_pred[mask], average="macro")
            wf1 = f1_score(df.loc[mask, target], y_pred[mask], average="weighted")
            print(
                f"  {lang}: n={mask.sum()}, Macro-F1={mf1:.4f}, Weighted-F1={wf1:.4f}"
            )
        print()


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    dev_df, val_df, val_pipelines = evaluate_validation()
    evaluate_critical_incident(dev_df, val_df)

    # Language-specific eval on validation set
    val_preds: dict[str, np.ndarray] = {}
    X_val = to_dicts(val_df)
    for target, pipe in val_pipelines.items():
        val_preds[target] = pipe.predict(X_val)
    evaluate_by_language(val_df, val_preds)

    evaluate_holdout()


if __name__ == "__main__":
    main()

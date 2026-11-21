"""Train and benchmark classification models for SentinelDesk ticket triage.

Loads the prepared training data, splits into development/validation sets,
and benchmarks individual models before ensemble decisions.
"""

import sys
from pathlib import Path

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ticket_features import make_ticket_features

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "prepared"
TRAIN_CSV = DATA_DIR / "train.csv"
MODEL_DIR = PROJECT_ROOT / "classification" / "models"

TARGETS = ("type", "queue", "priority")
RANDOM_STATE = 42
VAL_SIZE = 0.15  # 15 % of train.csv held for calibration / threshold tuning


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_training_data(path: Path = TRAIN_CSV) -> pd.DataFrame:
    """Load the prepared training CSV."""
    df = pd.read_csv(path)
    df["subject"] = df["subject"].fillna("")
    return df


def df_to_ticket_dicts(df: pd.DataFrame) -> list[dict[str, str]]:
    """Convert dataframe rows to the ticket dicts that ticket_features expects."""
    return df[["subject", "body"]].to_dict(orient="records")


# ---------------------------------------------------------------------------
# Model factories — each wraps make_ticket_features() so TF-IDF is fitted
# per cross-validation fold automatically.
# ---------------------------------------------------------------------------
def make_lr_pipeline() -> Pipeline:
    """Logistic Regression pipeline — native probability estimates."""
    features = make_ticket_features()
    features.steps.append(("clf", LogisticRegression(max_iter=1000, solver="saga")))
    return features


def make_svm_pipeline() -> Pipeline:
    """Linear SVM pipeline — Platt-scaled via CalibratedClassifierCV."""
    features = make_ticket_features()
    features.steps.append(
        ("clf", CalibratedClassifierCV(LinearSVC(max_iter=10_000), cv=5))
    )
    return features


def make_cnb_pipeline() -> Pipeline:
    """Complement Naive Bayes pipeline."""
    features = make_ticket_features()
    features.steps.append(("clf", ComplementNB(alpha=1.0)))
    return features


MODELS = {
    "lr": make_lr_pipeline,
    "svm": make_svm_pipeline,
    "cnb": make_cnb_pipeline,
}


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------
def evaluate_model(
    name: str,
    pipeline: Pipeline,
    X_dev: list[dict[str, str]],
    y_dev: pd.Series,
    X_val: list[dict[str, str]],
    y_val: pd.Series,
    target: str,
) -> dict:
    """Train on dev set, evaluate on validation set, return metrics dict."""
    print(f"\n--- {name.upper()} | target={target} ---")
    pipeline.fit(X_dev, y_dev)

    y_pred = pipeline.predict(X_val)
    macro_f1 = f1_score(y_val, y_pred, average="macro")
    weighted_f1 = f1_score(y_val, y_pred, average="weighted")

    print(f"Macro-F1:    {macro_f1:.4f}")
    print(f"Weighted-F1: {weighted_f1:.4f}")
    print(classification_report(y_val, y_pred, zero_division=0))

    return {
        "model": name,
        "target": target,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "predictions": y_pred,
    }


# ---------------------------------------------------------------------------
# Main training loop
# ---------------------------------------------------------------------------
def main() -> None:
    # 1. Load data
    print("Loading training data …")
    df = load_training_data()
    print(f"  {len(df)} tickets loaded")

    # 2. Dev / validation split (stratify on type, the most balanced target)
    dev_df, val_df = train_test_split(
        df,
        test_size=VAL_SIZE,
        random_state=RANDOM_STATE,
        stratify=df["type"],
    )
    print(f"  Dev set:  {len(dev_df)}  |  Val set: {len(val_df)}")

    X_dev = df_to_ticket_dicts(dev_df)
    X_val = df_to_ticket_dicts(val_df)

    # 3. Benchmark each base model on each target
    results: list[dict] = []

    for target in TARGETS:
        y_dev = dev_df[target]
        y_val = val_df[target]

        for model_name, factory in MODELS.items():
            pipeline = factory()
            metrics = evaluate_model(
                model_name, pipeline, X_dev, y_dev, X_val, y_val, target
            )
            results.append(metrics)

    # 4. Summary table
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    summary = pd.DataFrame(results)[["model", "target", "macro_f1", "weighted_f1"]]
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()

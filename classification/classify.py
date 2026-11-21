"""Ticket classification inference for SentinelDesk.

Train SVM pipelines on the full training set, save them to disk, and expose
a ``classify_ticket()`` function that the RAG pipeline and UI can call.
"""

import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from langdetect import LangDetectException, detect
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ticket_features import make_ticket_features

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "prepared"
TRAIN_CSV = DATA_DIR / "train.csv"
MODEL_DIR = PROJECT_ROOT / "classification" / "models"

TARGETS = ("type", "queue", "priority")
CRITICAL_INCIDENT_THRESHOLD = 0.3


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


def detect_language(text: str) -> str:
    try:
        lang = detect(text)
        return "de" if lang == "de" else "en"
    except LangDetectException:
        return "en"


def train_and_save() -> dict[str, Pipeline]:
    """Train one SVM pipeline per target on the full training set and save."""
    df = pd.read_csv(TRAIN_CSV)
    df["subject"] = df["subject"].fillna("")
    tickets = df[["subject", "body"]].to_dict(orient="records")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    pipelines: dict[str, Pipeline] = {}

    # Type is well-balanced — no class weighting needed.
    # Queue and priority need balanced weights to fix minority-class recall.
    target_weights: dict[str, str | None] = {
        "type": None,
        "queue": "balanced",
        "priority": "balanced",
    }

    for target in TARGETS:
        weight = target_weights[target]
        label = f"{target} (class_weight={weight})" if weight else target
        print(f"Training {label} classifier …")
        pipe = _make_svm_pipeline(class_weight=weight)
        pipe.fit(tickets, df[target])
        path = MODEL_DIR / f"svm_{target}.joblib"
        joblib.dump(pipe, path)
        pipelines[target] = pipe
        print(f"  Saved to {path}")

    # Critical incident binary classifier (Section 3.2)
    print("Training critical incident classifier …")
    df["critical"] = ((df["type"] == "Incident") & (df["priority"] == "high")).astype(
        int
    )
    pipe = _make_svm_pipeline(class_weight="balanced")
    pipe.fit(tickets, df["critical"])
    path = MODEL_DIR / "svm_critical.joblib"
    joblib.dump(pipe, path)
    pipelines["critical"] = pipe
    print(f"  Saved to {path}")

    return pipelines


def load_models(model_dir: Path = MODEL_DIR) -> dict[str, Pipeline]:
    """Load saved pipelines from disk."""
    pipelines: dict[str, Pipeline] = {}
    for target in (*TARGETS, "critical"):
        path = model_dir / f"svm_{target}.joblib"
        pipelines[target] = joblib.load(path)
    return pipelines


def classify_ticket(
    subject: str,
    body: str,
    pipelines: dict[str, Pipeline],
) -> dict:
    """Classify a single ticket and return structured output for RAG and UI.

    Returns the schema defined in classification_plan.md Section 9.2.
    """
    start = time.perf_counter()
    ticket = [{"subject": subject or "", "body": body}]
    detected_lang = detect_language(body)

    predictions: dict[str, str] = {}
    confidences: dict[str, float] = {}
    margins: dict[str, float] = {}

    for target in TARGETS:
        pipe = pipelines[target]
        proba = pipe.predict_proba(ticket)[0]
        classes = pipe.classes_
        top_idx = proba.argmax()
        sorted_proba = sorted(proba, reverse=True)

        predictions[target] = classes[top_idx]
        confidences[target] = round(float(sorted_proba[0]), 4)
        second = sorted_proba[1] if len(sorted_proba) > 1 else 0.0
        margins[target] = round(float(sorted_proba[0] - second), 4)

    # Critical incident risk from dedicated binary classifier (Section 3.2)
    critical_risk = 0.0
    if "critical" in pipelines:
        critical_proba = pipelines["critical"].predict_proba(ticket)[0]
        critical_classes = list(pipelines["critical"].classes_)
        if 1 in critical_classes:
            critical_risk = round(float(critical_proba[critical_classes.index(1)]), 4)

    is_critical_by_rule = (
        predictions["type"] == "Incident" and predictions["priority"] == "high"
    )

    # Escalation gate (Section 7.3) — four independent conditions
    escalation_reasons: list[str] = []

    # Condition 1: dedicated critical incident classifier
    if critical_risk >= CRITICAL_INCIDENT_THRESHOLD:
        escalation_reasons.append(f"High critical-incident risk ({critical_risk:.2f})")

    # Condition 2: rule-based backup (both classifiers agree)
    if is_critical_by_rule:
        escalation_reasons.append(
            "Predicted high-priority Incident (type + priority classifiers agree)"
        )

    # Condition 3: narrow classification margin
    for target in TARGETS:
        if margins[target] < 0.10:
            escalation_reasons.append(
                f"Narrow margin on {target} ({margins[target]:.2f})"
            )

    # Condition 4: low confidence fallback
    if confidences["type"] < 0.3:
        escalation_reasons.append(f"Low confidence on type ({confidences['type']:.2f})")

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    return {
        "predicted_type": predictions["type"],
        "predicted_queue": predictions["queue"],
        "predicted_priority": predictions["priority"],
        "confidence": confidences,
        "critical_incident_risk": critical_risk,
        "classification_margin": margins,
        "escalation": {
            "required": len(escalation_reasons) > 0,
            "reasons": escalation_reasons,
        },
        "detected_language": detected_lang,
        "inference_latency_ms": elapsed_ms,
    }


if __name__ == "__main__":
    print("Training classifiers on full training set …")
    pipelines = train_and_save()

    print("\nTest prediction:")
    result = classify_ticket(
        subject="VPN not connecting",
        body="I cannot connect to the corporate VPN since this morning. "
        "Multiple users in our office are affected. This is blocking all "
        "remote access to internal systems.",
        pipelines=pipelines,
    )
    for key, value in result.items():
        print(f"  {key}: {value}")

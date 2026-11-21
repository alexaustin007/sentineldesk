"""Score the triage workflow on the holdout split and write the console's metrics.json.

    python -m sentineldesk.evaluate_holdout

Two passes:
1. Labels and escalation for every holdout ticket, with no LLM calls.
2. The full live pipeline (Gemini) on a small random sample, for the status mix,
   latency, cost, and draft checks.

Only holdout subjects and bodies go into the workflow. Holdout labels are read
afterwards and used for scoring only.
"""

import hashlib
import json
import random
import time
from collections import defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from sentineldesk.app_factory import create_orchestrator
from sentineldesk.config import LABEL_HEADS, PREPARED_DATA_DIR, PROJECT_ROOT
from sentineldesk.llm import LLMRequest, LLMResponse, LLMUnavailableError
from sentineldesk.orchestrator import TriageOrchestrator
from sentineldesk.schemas import AUTO_DRAFT_READY, ESCALATE_IMMEDIATELY, HUMAN_REVIEW

METRICS_PATH = PROJECT_ROOT / "ui" / "public" / "metrics.json"
LIVE_SAMPLE_SIZE = 30
STATUS_KEYS = {
    AUTO_DRAFT_READY: "auto_draft",
    HUMAN_REVIEW: "human_review",
    ESCALATE_IMMEDIATELY: "escalate",
}
TARGET_RECALLS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


class OfflineLLM:
    """Refuses every call, so the labels pass never spends credits."""

    name = "offline"

    def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMUnavailableError("offline evaluation")


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(PREPARED_DATA_DIR / name, dtype=str, keep_default_na=False)


def predict_holdout(orchestrator: TriageOrchestrator) -> pd.DataFrame:
    """Run every holdout ticket through the labels and escalation stages."""
    rows = []
    for ticket in read_csv("holdout_inputs.csv").to_dict("records"):
        result = orchestrator.triage(ticket["subject"], ticket["body"])
        row: dict[str, Any] = {
            "ticket_id": ticket["ticket_id"],
            "escalated": result.status == ESCALATE_IMMEDIATELY,
            "incident_risk": result.incident_risk,
        }
        for head in LABEL_HEADS:
            row[f"predicted_{head}"] = result.final_labels.head(head).label
            row[f"confidence_{head}"] = result.final_labels.head(head).confidence
        rows.append(row)
    return pd.DataFrame(rows)


def head_metrics(scored: pd.DataFrame, head: str) -> dict[str, Any]:
    truth, predicted = scored[head], scored[f"predicted_{head}"]
    labels = sorted(set(truth))
    precision, recall, f1, support = precision_recall_fscore_support(
        truth, predicted, labels=labels, zero_division=0
    )
    correct = (truth == predicted).to_numpy()
    return {
        "macro_f1": round(
            f1_score(truth, predicted, labels=labels, average="macro"), 4
        ),
        "accuracy": round(accuracy_score(truth, predicted), 4),
        "labels": labels,
        "per_class": [
            {
                "label": label,
                "precision": round(float(p), 4),
                "recall": round(float(r), 4),
                "f1": round(float(score), 4),
                "support": int(count),
            }
            for label, p, r, score, count in zip(labels, precision, recall, f1, support)
        ],
        "confusion": confusion_matrix(truth, predicted, labels=labels).tolist(),
        "calibration_error": expected_calibration_error(
            scored[f"confidence_{head}"].to_numpy(), correct
        ),
        "macro_f1_by_language": {
            language: round(
                f1_score(
                    group[head],
                    group[f"predicted_{head}"],
                    labels=labels,
                    average="macro",
                ),
                4,
            )
            for language, group in scored.groupby("language")
            if language in ("en", "de")
        },
    }


def expected_calibration_error(
    confidence: np.ndarray, correct: np.ndarray, bins: int = 10
) -> float:
    """Average gap between confidence and accuracy, weighted by tickets per bin."""
    edges = np.linspace(0, 1, bins + 1)
    error = 0.0
    for low, high in pairwise(edges):
        in_bin = (confidence > low) & (confidence <= high)
        if in_bin.any():
            error += in_bin.mean() * abs(
                confidence[in_bin].mean() - correct[in_bin].mean()
            )
    return round(float(error), 4)


def escalation_tradeoff(
    scored: pd.DataFrame, truth: np.ndarray
) -> list[dict[str, Any]]:
    """Escalation rate needed to reach each recall, sweeping the incident-risk cutoff."""
    risk = scored["incident_risk"].to_numpy()
    rows = []
    for target in TARGET_RECALLS:
        for cutoff in sorted(set(np.round(risk, 4)), reverse=True):
            flagged = risk >= cutoff
            caught = int((flagged & truth).sum())
            if caught / truth.sum() >= target:
                rows.append(
                    {
                        "target_recall": target,
                        "escalation_rate": round(float(flagged.mean()), 4),
                        "precision": round(caught / int(flagged.sum()), 4),
                        "tickets_escalated": int(flagged.sum()),
                    }
                )
                break
    return rows


def leakage_counts(holdout_ids: set[str]) -> tuple[int, int]:
    """Holdout tickets found in the index by ID, and by normalised body text."""
    knowledge_base = read_csv("knowledge_base.csv")
    by_id = len(holdout_ids & set(knowledge_base["ticket_id"]))

    def body_hash(text: str) -> str:
        return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()

    index_bodies = {body_hash(body) for body in knowledge_base["body"]}
    holdout_bodies = [
        body_hash(body) for body in read_csv("holdout_inputs.csv")["body"]
    ]
    by_body = sum(body in index_bodies for body in holdout_bodies)
    return by_id, by_body


def live_pipeline_stats(orchestrator: TriageOrchestrator) -> dict[str, Any]:
    """Status mix, latency, cost, and draft checks on a random live sample."""
    inputs = read_csv("holdout_inputs.csv").to_dict("records")
    sample = random.Random(42).sample(inputs, LIVE_SAMPLE_SIZE)
    results = [
        orchestrator.triage(ticket["subject"], ticket["body"]) for ticket in sample
    ]

    statuses = [STATUS_KEYS[result.status] for result in results]
    stage_times: dict[str, list[float]] = defaultdict(list)
    cost_by_task: dict[str, float] = defaultdict(float)
    for result in results:
        for stage, milliseconds in result.stage_latency_ms.items():
            stage_times[stage].append(milliseconds)
        for call in result.llm_calls:
            cost_by_task[call.task] += call.estimated_cost_usd
    drafted = [result for result in results if result.draft_reply]
    latencies = [result.latency_ms for result in results]

    def share(condition_count: int) -> float | None:
        return round(condition_count / len(drafted), 4) if drafted else None

    return {
        "pipeline": {
            "status_mix": {
                key: round(statuses.count(key) / len(statuses), 4)
                for key in ("auto_draft", "human_review", "escalate")
            },
            "latency_ms": {
                "p50": round(float(np.percentile(latencies, 50)), 1),
                "p95": round(float(np.percentile(latencies, 95)), 1),
            },
            "stage_latency_ms": {
                stage: round(float(np.median(times)), 1)
                for stage, times in stage_times.items()
            },
            "avg_cost_usd": round(sum(cost_by_task.values()) / len(results), 6),
            "cost_breakdown_usd": {
                task: round(total / len(results), 6)
                for task, total in cost_by_task.items()
            },
            "cost_basis": (
                "Tokens reported by Gemini on Vertex AI times list prices per million "
                "tokens: Flash-Lite $0.30 in / $2.50 out, Flash $0.75 in / $3.75 out"
            ),
            "tickets": len(results),
        },
        "drafts": {
            "citations_valid_rate": share(
                sum(
                    not any("cite" in i for i in r.verification_issues) for r in drafted
                )
            ),
            "language_match_rate": share(
                sum(
                    not any("language" in i for i in r.verification_issues)
                    for r in drafted
                )
            ),
            "removed_claims_rate": share(sum(bool(r.removed_claims) for r in drafted)),
        },
    }


def main() -> None:
    started = time.perf_counter()
    live = create_orchestrator()
    offline = TriageOrchestrator(
        classifier=live.classifier,
        precedent_index=live.precedent_index,
        llm_provider=OfflineLLM(),
        config=live.config,
    )

    predictions = predict_holdout(offline)
    print(
        f"Labeled {len(predictions)} holdout tickets in {time.perf_counter() - started:.0f}s"
    )
    # Holdout labels are read only now, after every prediction exists.
    scored = predictions.merge(read_csv("holdout_labels.csv"), on="ticket_id")
    truth = (
        scored["priority"].str.lower().isin(live.config.high_priority_labels)
        & (scored["type"] == live.config.incident_type_label)
    ).to_numpy()
    caught = int((scored["escalated"].to_numpy() & truth).sum())
    by_id, by_body = leakage_counts(set(scored["ticket_id"]))
    heads = {head: head_metrics(scored, head) for head in LABEL_HEADS}

    metrics: dict[str, Any] = {
        "sample": False,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": (
            "Calibrated TF-IDF + LinearSVC classifier blended with a "
            "similarity-weighted precedent vote (multilingual MiniLM + FAISS), "
            "before the Gemini reviewer"
        ),
        "dataset": "dataset-tickets-multi-lang-4-20k.csv",
        "split": {
            "train": len(read_csv("train.csv")),
            "knowledge_base": len(live.precedent_index.tickets),
            "holdout": len(scored),
            "leakage_check": f"{by_id} of {len(scored):,} holdout ticket IDs are in the index",
            "leakage_detail": (
                "Ticket IDs and SHA-256 hashes of each normalised holdout body were "
                f"checked against the knowledge base: {by_id} ID matches and {by_body} "
                "body matches (the source data repeats some message texts). The index "
                "build refuses to run if any holdout ID is present."
            ),
        },
        "heads": heads,
        "calibration_error": round(
            float(np.mean([head["calibration_error"] for head in heads.values()])), 4
        ),
        "high_priority_incident_recall": round(caught / int(truth.sum()), 4),
        "high_priority_incident": {
            "caught": caught,
            "total": int(truth.sum()),
            "escalation_rate": round(float(scored["escalated"].mean()), 4),
        },
        "escalation_tradeoff": escalation_tradeoff(scored, truth),
    }
    print(f"Running the live pipeline on {LIVE_SAMPLE_SIZE} sampled holdout tickets...")
    metrics.update(live_pipeline_stats(live))

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    summary = {head: values["macro_f1"] for head, values in heads.items()}
    print(
        f"Macro-F1 {summary}; high-priority incident recall {metrics['high_priority_incident_recall']}"
    )
    print(f"Wrote {METRICS_PATH} in {time.perf_counter() - started:.0f}s")


if __name__ == "__main__":
    main()

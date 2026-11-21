"""Measure the precedent agent on a validation slice of the historical split.

    python -m sentineldesk.rag_validation

A seeded slice of historical tickets plays the role of new tickets. The rest are
indexed, and the report shows how well the similarity-weighted vote predicts each
label, how well the precedent agent alone catches high-priority incidents, and how
similar the best match usually is. No holdout data is used, so thresholds may be
tuned from these numbers.
"""

import json
import time

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

from sentineldesk.config import LABEL_HEADS, TriageConfig
from sentineldesk.data_interface import load_historical_tickets
from sentineldesk.escalation import high_priority_incident_share
from sentineldesk.precedent_vote import strongest_similarity, vote_on_labels
from sentineldesk.retrieval import PrecedentIndex, create_embedder
from sentineldesk.schemas import ticket_text


def validate_precedent_agent(
    sample_size: int = 500, seed: int = 42, config: TriageConfig | None = None
) -> dict[str, object]:
    config = config or TriageConfig()
    historical = load_historical_tickets()
    validation = historical.sample(n=sample_size, random_state=seed)
    index = PrecedentIndex.build(historical.drop(validation.index), create_embedder())

    predicted: dict[str, list[str]] = {head: [] for head in LABEL_HEADS}
    top_similarities, flagged = [], []
    started = time.perf_counter()
    for ticket in validation.to_dict("records"):
        precedents = index.search(
            ticket_text(ticket["subject"], ticket["body"]), config.retrieval_top_k
        )
        vote = vote_on_labels(precedents)
        for head in LABEL_HEADS:
            predicted[head].append(vote.head(head).label if vote else "")
        top_similarities.append(strongest_similarity(precedents))
        share = high_priority_incident_share(precedents, config)
        flagged.append(share >= config.min_incident_precedent_share)
    seconds_per_ticket = (time.perf_counter() - started) / sample_size

    is_high_priority_incident = (
        validation["priority"].str.lower().isin(config.high_priority_labels)
        & (validation["type"] == config.incident_type_label)
    ).tolist()
    caught = sum(f and truth for f, truth in zip(flagged, is_high_priority_incident))
    return {
        "validation_tickets": sample_size,
        "indexed_tickets": len(index.tickets),
        "embedder": index.embedder.name,
        "labels": {
            head: {
                "accuracy": round(accuracy_score(validation[head], predicted[head]), 3),
                "macro_f1": round(
                    f1_score(validation[head], predicted[head], average="macro"), 3
                ),
            }
            for head in LABEL_HEADS
        },
        "high_priority_incidents": {
            "actual": sum(is_high_priority_incident),
            "flagged": sum(flagged),
            "recall": round(caught / max(sum(is_high_priority_incident), 1), 3),
            "precision": round(caught / max(sum(flagged), 1), 3),
        },
        "top_similarity_percentiles": {
            f"p{percentile}": round(
                float(np.percentile(top_similarities, percentile)), 3
            )
            for percentile in (5, 10, 25, 50, 75)
        },
        "retrieval_ms_per_ticket": round(seconds_per_ticket * 1000, 1),
    }


if __name__ == "__main__":
    print(json.dumps(validate_precedent_agent(), indent=2))

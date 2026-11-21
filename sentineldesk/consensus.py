"""Double-agent consensus: blend the classifier with the RAG vote, list disagreements."""

from collections.abc import Sequence
from dataclasses import replace

from sentineldesk.config import LABEL_HEADS
from sentineldesk.schemas import LabelDistribution, TicketLabels


def blend_predictions(
    classifier_labels: TicketLabels,
    rag_labels: TicketLabels | None,
    classifier_weight: float,
) -> TicketLabels:
    """Weighted average of the two agents' probabilities for each head.

    Without precedents the classifier stands alone. `find_disagreements` flags
    the missing evidence separately.
    """
    if rag_labels is None:
        return replace(classifier_labels, source="combined")
    distributions = {
        head: blend_distributions(
            classifier_labels.head(head), rag_labels.head(head), classifier_weight
        )
        for head in LABEL_HEADS
    }
    return TicketLabels(source="combined", **distributions)


def blend_distributions(
    first: LabelDistribution, second: LabelDistribution, first_weight: float
) -> LabelDistribution:
    """Mix two distributions; labels missing from one count as probability 0."""
    labels = sorted(set(first.probabilities) | set(second.probabilities))
    blended = {
        label: first_weight * first.probabilities.get(label, 0.0)
        + (1 - first_weight) * second.probabilities.get(label, 0.0)
        for label in labels
    }
    ranked = sorted(blended.items(), key=lambda item: item[1], reverse=True)
    return LabelDistribution(dict(ranked))


def find_disagreements(
    classifier_labels: TicketLabels,
    rag_labels: TicketLabels | None,
    heads: Sequence[str],
) -> list[str]:
    """Describe each head where the two agents pick different labels."""
    if rag_labels is None:
        return ["no historical precedents were available to check the classifier"]
    disagreements = []
    for head in heads:
        classifier_label = classifier_labels.head(head).label
        precedent_label = rag_labels.head(head).label
        if classifier_label != precedent_label:
            disagreements.append(
                f"{head}: classifier says '{classifier_label}', "
                f"precedents say '{precedent_label}'"
            )
    return disagreements

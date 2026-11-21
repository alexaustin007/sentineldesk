"""Compare classifier predictions with independent historical evidence."""

from collections.abc import Sequence

from sentineldesk.schemas import LabelDistribution, TicketLabels


def blend_predictions(
    classifier_labels: TicketLabels,
    rag_labels: TicketLabels | None,
    classifier_weight: float | None = None,
) -> TicketLabels:
    """Return the authoritative classifier predictions unchanged.

    This compatibility wrapper intentionally does *not* blend the distributions.
    Calibrated classifier probabilities and similarity-weighted RAG vote shares
    have different meanings, so averaging them creates a score that is neither.
    Keep ``rag_labels`` as a separate evidence signal and use
    :func:`find_disagreements` to compare the two branches.

    ``classifier_weight`` remains temporarily accepted so older callers fail
    safely while migrating; its value has no effect.
    """
    _ = rag_labels, classifier_weight
    return classifier_labels


def blend_distributions(
    first: LabelDistribution,
    second: LabelDistribution,
    first_weight: float | None = None,
) -> LabelDistribution:
    """Compatibility wrapper that preserves the calibrated distribution.

    New code should keep ``second`` visible as a separate RAG vote rather than
    calling this function.
    """
    _ = second, first_weight
    return first


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

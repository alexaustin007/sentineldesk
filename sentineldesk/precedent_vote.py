"""RAG agent: check the classifier by letting similar past tickets vote on the labels."""

from collections import defaultdict
from collections.abc import Sequence

from sentineldesk.config import LABEL_HEADS
from sentineldesk.schemas import LabelDistribution, Precedent, TicketLabels


def credible_precedents(
    precedents: Sequence[Precedent], min_similarity: float
) -> list[Precedent]:
    """Keep only neighbors strong enough to vote, support, or be cited."""
    return [
        precedent for precedent in precedents if precedent.similarity >= min_similarity
    ]


def vote_on_labels(precedents: Sequence[Precedent]) -> TicketLabels | None:
    """Similarity-weighted vote of the retrieved precedents for each head.

    Each precedent votes for its own type, queue, and priority with a weight equal
    to its cosine similarity. Negative similarities count as zero. Returns None
    when no precedent carries any weight.
    """
    weights = similarity_weights(precedents)
    total_weight = sum(weights)
    if total_weight == 0:
        return None

    distributions = {}
    for head in LABEL_HEADS:
        votes: dict[str, float] = defaultdict(float)
        for precedent, weight in zip(precedents, weights):
            votes[getattr(precedent, head)] += weight
        ranked = sorted(votes.items(), key=lambda item: item[1], reverse=True)
        distributions[head] = LabelDistribution(
            {label: score / total_weight for label, score in ranked}
        )
    return TicketLabels(source="rag_vote", **distributions)


def similarity_weights(precedents: Sequence[Precedent]) -> list[float]:
    """Voting weight of each precedent: its cosine similarity, floored at zero."""
    return [max(precedent.similarity, 0.0) for precedent in precedents]


def strongest_similarity(precedents: Sequence[Precedent]) -> float:
    """Similarity of the best match, or 0.0 when nothing was retrieved."""
    return max((precedent.similarity for precedent in precedents), default=0.0)

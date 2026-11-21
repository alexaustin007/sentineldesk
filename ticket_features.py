"""TF-IDF features for English and German support tickets."""

from collections.abc import Iterable, Mapping

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer


def ticket_texts(tickets: Iterable[Mapping[str, str | None]]) -> list[str]:
    """Return one document per ticket, keeping input order and using only its text."""
    documents = []
    for ticket in tickets:
        subject = (ticket.get("subject") or "").strip()
        body = (ticket["body"] or "").strip()
        if not body:
            raise ValueError("Each ticket must have a nonblank body")
        documents.append(f"{subject}\n{body}".strip())
    return documents


def make_ticket_features() -> Pipeline:
    """Create an unfitted pipeline combining word and character n-gram TF-IDF."""
    return Pipeline(
        [
            ("text", FunctionTransformer(ticket_texts, validate=False)),
            (
                "tfidf",
                FeatureUnion(
                    [
                        (
                            "word",
                            TfidfVectorizer(
                                analyzer="word",
                                ngram_range=(1, 2),
                                sublinear_tf=True,
                                max_features=50_000,
                                min_df=2,
                            ),
                        ),
                        (
                            "char",
                            TfidfVectorizer(
                                analyzer="char_wb",
                                ngram_range=(3, 5),
                                sublinear_tf=True,
                                max_features=50_000,
                                min_df=2,
                            ),
                        ),
                    ]
                ),
            ),
        ]
    )

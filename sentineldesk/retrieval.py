"""Historical retrieval (RAG): embed past tickets and find the closest precedents.

The same index serves two purposes:
1. Evidence for grounded replies (the precedents' answers).
2. An independent check on the classifier (see precedent_vote.py).
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

import faiss
import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from sentineldesk.config import LABEL_HEADS
from sentineldesk.data_interface import validate_historical_tickets
from sentineldesk.schemas import Precedent, clean_text, ticket_text

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class TextEmbedder(Protocol):
    """Turns texts into unit-length vectors, so inner product is cosine similarity."""

    name: str

    def fit(self, texts: Sequence[str]) -> None: ...

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Multilingual sentence embeddings, so a German ticket can match an English one."""

    def __init__(self, model_name: str | None = None) -> None:
        self.name = model_name or os.getenv(
            "SENTINEL_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        )
        self._model = None

    def fit(self, texts: Sequence[str]) -> None:
        """Pretrained model, so there is nothing to fit."""

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if self._model is None:
            # Imported here because loading torch is slow and tests do not need it.
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.name)
        vectors = self._model.encode(
            list(texts),
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 500,
        )
        return np.ascontiguousarray(vectors, dtype=np.float32)

    def __getstate__(self) -> dict[str, object]:
        # Save only the model name. The weights reload from the Hugging Face cache.
        return {"name": self.name, "_model": None}


class TfidfEmbedder:
    """Offline embedder: character TF-IDF, reduced with SVD on large corpora.

    It needs no model download, so it suits tests and the mock data. It cannot
    match across languages; use SentenceTransformerEmbedder for the real index.
    """

    def __init__(self, dimensions: int = 256) -> None:
        self.name = "tfidf"
        self.dimensions = dimensions
        self._vectorizer = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True
        )
        self._svd: TruncatedSVD | None = None

    def fit(self, texts: Sequence[str]) -> None:
        matrix = self._vectorizer.fit_transform(texts)
        # Reduce dimensions only when the corpus is large enough for it to help.
        if min(matrix.shape) > self.dimensions:
            self._svd = TruncatedSVD(n_components=self.dimensions, random_state=42)
            self._svd.fit(matrix)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        matrix = self._vectorizer.transform(texts)
        vectors = self._svd.transform(matrix) if self._svd else matrix.toarray()
        return np.ascontiguousarray(normalize(vectors), dtype=np.float32)


def mix_languages(
    precedents: Sequence[Precedent],
    count: int,
    language: str,
    min_other_language: int,
    min_similarity: float,
) -> list[Precedent]:
    """Pick `count` precedents, keeping slots for strong matches in other languages.

    Same-language tickets usually score a little higher, so without this a German
    ticket would rarely see the English resolution that answers it best.
    """
    other_language = [
        precedent
        for precedent in precedents
        if precedent.language != language and precedent.similarity >= min_similarity
    ][:min_other_language]
    remaining = [
        precedent for precedent in precedents if precedent not in other_language
    ]
    chosen = other_language + remaining[: count - len(other_language)]
    return sorted(chosen, key=lambda precedent: precedent.similarity, reverse=True)


def create_embedder(kind: str | None = None) -> TextEmbedder:
    """Pick an embedder: "sentence-transformers" (default) or "tfidf"."""
    kind = (kind or os.getenv("SENTINEL_EMBEDDER", "sentence-transformers")).lower()
    if kind == "tfidf":
        return TfidfEmbedder()
    if kind == "sentence-transformers":
        return SentenceTransformerEmbedder()
    raise ValueError(
        f"Unknown embedder '{kind}'. Use 'sentence-transformers' or 'tfidf'."
    )


class PrecedentIndex:
    """FAISS index over historical tickets. Build it from the historical split only."""

    def __init__(
        self, tickets: pd.DataFrame, embedder: TextEmbedder, index: faiss.Index
    ) -> None:
        self.tickets = tickets
        self.embedder = embedder
        self.index = index

    @classmethod
    def build(
        cls,
        historical_tickets: pd.DataFrame,
        embedder: TextEmbedder,
        holdout_ticket_ids: Iterable[str] = (),
    ) -> PrecedentIndex:
        """Embed every historical ticket. Pass holdout IDs to prove none are indexed."""
        tickets = validate_historical_tickets(historical_tickets, holdout_ticket_ids)
        texts = [
            ticket_text(subject, body)
            for subject, body in zip(tickets["subject"], tickets["body"])
        ]
        embedder.fit(texts)
        vectors = embedder.embed(texts)
        # Inner product of unit vectors is cosine similarity.
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return cls(tickets, embedder, index)

    def search(self, query_text: str, top_k: int = 10) -> list[Precedent]:
        """Return the `top_k` most similar historical tickets, most similar first."""
        top_k = min(top_k, self.index.ntotal)
        if top_k == 0 or not query_text.strip():
            return []
        similarities, rows = self.index.search(self.embedder.embed([query_text]), top_k)
        return [
            self._precedent(row, similarity)
            for row, similarity in zip(rows[0], similarities[0])
            if row >= 0
        ]

    def label_options(self) -> dict[str, list[str]]:
        """Labels that occur in the historical tickets, per head."""
        return {
            head: sorted(self.tickets[head].dropna().astype(str).unique())
            for head in LABEL_HEADS
        }

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / "index.faiss"))
        self.tickets.to_json(
            directory / "tickets.jsonl", orient="records", lines=True, force_ascii=False
        )
        joblib.dump(self.embedder, directory / "embedder.joblib")

    @classmethod
    def load(cls, directory: Path) -> PrecedentIndex:
        """Load an index written by `save`. joblib uses pickle: load only your own files."""
        index = faiss.read_index(str(directory / "index.faiss"))
        # dtype=False keeps ticket IDs and labels as plain strings.
        tickets = pd.read_json(
            directory / "tickets.jsonl", orient="records", lines=True, dtype=False
        )
        embedder = joblib.load(directory / "embedder.joblib")
        return cls(tickets, embedder, index)

    def _precedent(self, row: int, similarity: float) -> Precedent:
        record = self.tickets.iloc[int(row)]
        return Precedent(
            ticket_id=str(record["ticket_id"]),
            similarity=float(similarity),
            subject=clean_text(record["subject"]),
            body=clean_text(record["body"]),
            answer=clean_text(record["answer"]),
            type=clean_text(record["type"]),
            queue=clean_text(record["queue"]),
            priority=clean_text(record["priority"]),
            language=clean_text(record["language"]),
        )

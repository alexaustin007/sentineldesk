"""Build the precedent index from the official historical split and save it.

    python -m sentineldesk.build_index

Run `python3 scripts/prepare_data.py` first. The index is saved to
artifacts/precedent_index, so the console loads it in seconds instead of
re-embedding every historical ticket at startup.
"""

import time
from pathlib import Path

from sentineldesk.config import INDEX_DIR
from sentineldesk.data_interface import (
    has_prepared_data,
    load_historical_tickets,
    load_holdout_ticket_ids,
)
from sentineldesk.retrieval import PrecedentIndex, create_embedder


def build_and_save_index(
    index_dir: Path = INDEX_DIR, embedder_kind: str | None = None
) -> PrecedentIndex:
    if not has_prepared_data():
        raise SystemExit(
            "data/prepared/ is missing. Run scripts/prepare_data.py first."
        )
    started = time.perf_counter()
    holdout_ids = load_holdout_ticket_ids()
    index = PrecedentIndex.build(
        load_historical_tickets(),
        create_embedder(embedder_kind),
        holdout_ticket_ids=holdout_ids,
    )
    index.save(index_dir)
    print(
        f"Indexed {len(index.tickets)} historical tickets with {index.embedder.name} "
        f"in {time.perf_counter() - started:.0f}s. "
        f"None of the {len(holdout_ids)} holdout tickets were included. "
        f"Saved to {index_dir}."
    )
    return index


if __name__ == "__main__":
    build_and_save_index()

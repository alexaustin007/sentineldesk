"""Build the local SentinelDesk training, retrieval, and evaluation CSVs."""

import argparse
import csv
import random
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA_DIR / "dataset-tickets-multi-lang-4-20k.csv"
V5_SOURCE = DATA_DIR / "aa_dataset-tickets-multi-lang-5-2-50-version.csv"
GERMAN_SOURCE = DATA_DIR / "dataset-tickets-german_normalized_50_5_2.csv"
INPUT_FIELDS = ("ticket_id", "subject", "body")
LABEL_FIELDS = ("type", "queue", "priority", "language")
KB_FIELDS = (*INPUT_FIELDS, "answer", "language")


def read_tickets(source: Path, prefix: str = "TKT") -> list[dict[str, str]]:
    tickets = []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"subject", "body", "answer", *LABEL_FIELDS}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

        for number, row in enumerate(reader, start=1):
            if None in row or any(row[field] is None for field in required):
                raise ValueError(f"Invalid column count in record {number}")
            if not row["body"].strip():
                continue
            ticket = {field: row[field].strip() for field in required}
            ticket["ticket_id"] = f"{prefix}-{number:05d}"
            if any(not ticket[field] for field in LABEL_FIELDS):
                raise ValueError(f"Missing label in {ticket['ticket_id']}")
            tickets.append(ticket)
    return tickets


def write_csv(
    path: Path, fields: tuple[str, ...], rows: Iterable[dict[str, str]]
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in rows)


def split_prototype(
    tickets: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if len(tickets) < 2:
        raise ValueError("At least two tickets with a body are required for the split")
    shuffled = tickets.copy()
    random.Random(42).shuffle(shuffled)
    cutoff = len(shuffled) * 4 // 5
    return shuffled[:cutoff], shuffled[cutoff:]


def normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def split_full(data_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    # This source has queue and priority but neither type nor a historical answer.
    with (data_dir / GERMAN_SOURCE.name).open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        reader = csv.DictReader(stream)
        if {"type", "answer"}.intersection(reader.fieldnames or ()):
            raise ValueError(
                "German source schema changed. Check its eligibility before splitting."
            )
        excluded = sum(1 for _ in reader)
    print(f"Excluded {excluded} German records without type or resolution.")

    prototype = read_tickets(data_dir / SOURCE.name)
    newer = read_tickets(data_dir / V5_SOURCE.name, prefix="TKT-V5")
    old_train, old_holdout = split_prototype(prototype)
    train_bodies = {normalize(row["body"]) for row in old_train}
    holdout_bodies = {normalize(row["body"]) for row in old_holdout} - train_bodies

    # Preserve the prototype ID and labels for repeated inputs. Fill a blank
    # historical resolution only when another copy supplies one.
    unique = {}
    for row in [*prototype, *newer]:
        key = (normalize(row["subject"]), normalize(row["body"]))
        kept = unique.setdefault(key, row)
        if not kept["answer"]:
            kept["answer"] = row["answer"]

    groups: dict[str, list[dict[str, str]]] = {}
    for (_, body), row in unique.items():
        groups.setdefault(body, []).append(row)

    historical = []
    holdout = []
    new_groups = []
    for body, group in groups.items():
        if body in train_bodies:
            historical.extend(group)
        elif body in holdout_bodies:
            holdout.extend(group)
        else:
            new_groups.append(group)

    # Assign unseen body groups together until the holdout reaches 20%.
    target = len(unique) - len(unique) * 4 // 5
    rng = random.Random(42)
    rng.shuffle(new_groups)
    for group in new_groups:
        if len(holdout) < target:
            holdout.extend(group)
        else:
            historical.extend(group)
    rng.shuffle(historical)
    rng.shuffle(holdout)
    print(
        f"Kept {len(unique)} distinct labeled inputs from {len(prototype) + len(newer)} usable rows."
    )
    return historical, holdout


def write_split(
    historical: list[dict[str, str]], holdout: list[dict[str, str]], output_dir: Path
) -> None:
    resolved = [ticket for ticket in historical if ticket["answer"]]

    output_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir) as temp:
        stage = Path(temp)
        write_csv(stage / "train.csv", (*INPUT_FIELDS, *LABEL_FIELDS), historical)
        write_csv(stage / "knowledge_base.csv", KB_FIELDS, resolved)
        write_csv(stage / "holdout_inputs.csv", INPUT_FIELDS, holdout)
        write_csv(stage / "holdout_labels.csv", ("ticket_id", *LABEL_FIELDS), holdout)
        for path in stage.iterdir():
            path.replace(output_dir / path.name)

    print(
        f"{len(historical)} training, {len(resolved)} retrieval, {len(holdout)} holdout tickets in {output_dir}"
    )


def prepare_data(source: Path, output_dir: Path) -> None:
    """Reproduce the original 20K split."""
    write_split(*split_prototype(read_tickets(source)), output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("full", "20k"), default="full")
    args = parser.parse_args()
    if args.dataset == "full":
        write_split(*split_full(DATA_DIR), DATA_DIR / "prepared")
    else:
        prepare_data(SOURCE, DATA_DIR / "prepared")

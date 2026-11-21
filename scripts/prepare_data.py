"""Build the local SentinelDesk training, retrieval, and evaluation CSVs."""

import csv
import random
from collections.abc import Iterable
from pathlib import Path
from tempfile import TemporaryDirectory

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SOURCE = DATA_DIR / "dataset-tickets-multi-lang-4-20k.csv"
INPUT_FIELDS = ("ticket_id", "subject", "body")
LABEL_FIELDS = ("type", "queue", "priority", "language")
KB_FIELDS = (*INPUT_FIELDS, "answer", "language")


def read_tickets(source: Path) -> list[dict[str, str]]:
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
            ticket["ticket_id"] = f"TKT-{number:05d}"
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


def prepare_data(source: Path, output_dir: Path) -> None:
    tickets = read_tickets(source)
    if len(tickets) < 2:
        raise ValueError("At least two tickets with a body are required for the split")
    random.Random(42).shuffle(tickets)
    cutoff = len(tickets) * 4 // 5
    historical, holdout = tickets[:cutoff], tickets[cutoff:]
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


if __name__ == "__main__":
    prepare_data(SOURCE, DATA_DIR / "prepared")

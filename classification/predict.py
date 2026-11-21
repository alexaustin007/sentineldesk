"""Generate classification predictions for the holdout set.

Loads the trained SVM models, runs inference on every ticket in
holdout_inputs.csv, and writes the results to holdout_predictions.json.
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from classification.classify import classify_ticket, load_models

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "prepared"
HOLDOUT_INPUTS = DATA_DIR / "holdout_inputs.csv"
OUTPUT_PATH = DATA_DIR / "holdout_predictions.json"


def main() -> None:
    print("Loading models …")
    pipelines = load_models()

    print("Loading holdout inputs …")
    df = pd.read_csv(HOLDOUT_INPUTS)
    df["subject"] = df["subject"].fillna("")
    print(f"  {len(df)} holdout tickets")

    predictions = []
    for i, row in df.iterrows():
        result = classify_ticket(
            subject=row["subject"],
            body=row["body"],
            pipelines=pipelines,
        )
        result["ticket_id"] = row["ticket_id"]
        predictions.append(result)

        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{len(df)} classified")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(predictions, f, indent=2, ensure_ascii=False)

    print(f"\nWrote {len(predictions)} predictions to {OUTPUT_PATH}")

    escalated = sum(1 for p in predictions if p["escalation"]["required"])
    print(
        f"Escalation rate: {escalated}/{len(predictions)} ({escalated / len(predictions) * 100:.1f}%)"
    )

    for target in ("predicted_type", "predicted_queue", "predicted_priority"):
        counts = {}
        for p in predictions:
            val = p[target]
            counts[val] = counts.get(val, 0) + 1
        print(f"\n{target}:")
        for val, count in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {val}: {count}")


if __name__ == "__main__":
    main()

from datasets import load_dataset


def main() -> None:
    dataset = load_dataset("Tobi-Bueck/customer-support-tickets")
    print(dataset)


if __name__ == "__main__":
    main()

# 1. Type — Incident, Request, Problem, or Change.
# 2. Queue — Which department should handle the ticket (IT Support, Billing, Sales, etc.).
# 3. Priority — High, medium, or low.
# For each prediction, you must also provide a confidence score.










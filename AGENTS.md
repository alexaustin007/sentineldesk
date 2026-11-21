# Working on SentinelDesk

Follow these guidelines when adding or changing code. See the [contributor instructions](README.md#contributing) for setup and checks.

## Python style

- Use four spaces per indentation level and let Ruff format Python files.
- Use descriptive `snake_case` names for functions and variables. Add type hints for function parameters and return values.
- Keep ticket classification, historical retrieval, escalation decisions, and reply generation in focused modules. Keep the UI responsible for gathering input and displaying results.
- Reuse existing functions and interfaces where they fit. Keep changes focused so teammates can review them quickly.

## Dataset and evaluation

- Download the organizer-provided CSV using the [dataset instructions](README.md#hackathon-dataset). Keep the downloaded CSV local.
- Make a reproducible 80/20 split before training or indexing. Train and build the retrieval index from the historical 80%.
- Give the app only the ticket subject and body during holdout evaluation. Use holdout labels only for scoring and keep holdout answers out of training, retrieval, and prompts.

## Before opening a pull request

- Run `ruff format .`, `ruff check .`, and `ruff format --check .` from the repository root.
- Verify the behavior you changed and describe how you checked it in the pull request.

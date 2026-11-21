# SentinelDesk

SentinelDesk is a hackathon project for multilingual incident triage and
evidence-backed resolution drafts.

## Setup

Use an isolated Python 3.12 environment. This keeps NumPy and compiled
dependencies such as PyArrow binary-compatible with each other. The Conda
`base` environment from the reported error mixes NumPy 2 with extensions that
were compiled for NumPy 1.

```bash
python --version  # expected: Python 3.12.x
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python sentineldesk.py
```

Do not install these dependencies into Conda's `base` environment. If the
virtual environment already exists, activate it and run only the final two
commands.

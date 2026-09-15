# Synthetic Data AI

AI-assisted generation of consistent synthetic data for relational schemas.

## Status

The repository foundation is in place. Feature implementation is proceeding in small,
reviewable stages: schema parsing, deterministic relational generation, persistence, Gemini
planning, Streamlit UI, data chat, and Langfuse tracing.

## Architecture

```text
Streamlit UI
    ↓
Application use cases
    ↓
Domain models and deterministic rules
    ↓
Infrastructure adapters (database, Vertex AI, Langfuse)
```

The LLM proposes a validated generation plan and interprets questions. Deterministic Python
code owns data generation, referential integrity, and database writes. Raw LLM SQL is never
executed.

## Requirements

- Python 3.12
- Optional: Docker for the PostgreSQL development profile
- Google Cloud access to project `gd-gcp-gridu-genai` for live Gemini calls

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Run the current application shell:

```bash
streamlit run app.py
```

Run quality checks:

```bash
make check
```

## Configuration safety

Use `.env` only for local configuration. It is ignored by Git. Vertex AI authentication uses
Google Application Default Credentials; never commit service-account JSON files or API keys.


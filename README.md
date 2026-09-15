# Synthetic Data AI

A Streamlit application that reads PostgreSQL DDL, creates realistic synthetic relational
data, preserves primary/foreign-key integrity, stores the result, and answers safe analytical
questions. Gemini proposes typed plans; deterministic Python validates and executes them.

## What the application demonstrates

- PostgreSQL DDL parsing into typed Pydantic domain models
- deterministic, reproducible generation with Faker and a seed
- dependency-ordered table generation with primary, foreign, unique, and nullable constraints
- structured Gemini output through the Google Gen AI SDK and Vertex AI authentication
- SQLite zero-setup persistence and optional PostgreSQL persistence
- natural-language analytics without executing LLM-authored SQL
- optional Langfuse traces for Gemini planning calls
- a Streamlit UI for generation, preview, CSV export, analytics, and charts

## Architecture and responsibility boundaries

```text
Streamlit UI
    -> application use cases and validation
        -> Pydantic domain models and deterministic generator
            -> Google Gen AI SDK / SQLAlchemy / Langfuse adapters
```

| Component | Responsibility |
| --- | --- |
| Streamlit | Collect DDL, request, settings, and display results |
| Gemini | Convert natural language into a constrained `GenerationPlan` or `QueryPlan` |
| Pydantic | Validate every plan before it reaches generation or persistence |
| Python generator | Create repeatable data and maintain relational integrity |
| SQLAlchemy | Create tables, persist rows, and build allowlisted analytical queries |
| SQLite/PostgreSQL | Store generated tables |
| Langfuse | Record AI prompts, models, results, timing, and errors when enabled |

Gemini never writes to the database and raw LLM SQL is never executed. Query plans support a
small allowlist such as preview, count, average, sum, and grouped averages.

## Fast local demo (no Docker, GCP, or Langfuse required)

Requirements: Python 3.12.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
streamlit run app.py
```

Open `http://localhost:8501`, keep both Gemini toggles off, and click **Generate relational
dataset**. The offline planner creates the same validated plan shape without a network call.
SQLite stores the result in `synthetic_data.db`; this generated file is ignored by Git.

## Enable Gemini through Vertex AI

The course project is configured for `gd-gcp-gridu-genai` and `gemini-2.5-flash`. Install the
Google Cloud CLI, then authenticate with the corporate Google account that has project access:

```bash
gcloud auth login
gcloud config set project gd-gcp-gridu-genai
gcloud auth application-default login
```

The first command authenticates the CLI. The second chooses the GridU billing/quota project.
The third creates local Application Default Credentials used automatically by the Google Gen
AI SDK. No API key or service-account JSON is needed.

Confirm `.env` contains:

```dotenv
GOOGLE_CLOUD_PROJECT=gd-gcp-gridu-genai
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=true
SYNTH_GEMINI_MODEL=gemini-2.5-flash
```

Restart Streamlit and enable **Use Gemini planning through Vertex AI**. The generated plan is
still validated by Pydantic before deterministic Python creates any rows.

## Optional Langfuse observability

Create a Langfuse project and add its keys only to the local `.env` file:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

When both keys are present, Gemini planning calls are traced automatically. Without them,
tracing becomes a no-op and the application continues normally. Generated table contents are
not sent to Langfuse.

## Optional PostgreSQL profile

SQLite is enough for the course demo. If Docker is available, start PostgreSQL with:

```bash
docker compose up -d postgres
```

Then set:

```dotenv
SYNTH_DATABASE_URL=postgresql+psycopg://synthetic_user:local-development-only@localhost:5432/synthetic_data
```

Stop and remove course resources when finished:

```bash
docker compose down -v
```

## Quality checks

```bash
make check
```

This runs Ruff linting and formatting checks, strict Mypy type checking, and Pytest. GitHub
Actions repeats the same checks on every pull request and push to `main`.

Current automated coverage includes configuration, DDL parsing, generation determinism,
foreign-key integrity, persistence, safe analytics, Gemini structured responses, guardrails,
and optional tracing.

## Suggested course demonstration

1. Paste or keep the sample two-table DDL.
2. Describe a European technology company and generate 100 employees with seed `42`.
3. Show the four result metrics and preview both related tables.
4. Export a table from **Data explorer**.
5. Ask: `What is the average salary by country in employees?`
6. Show the result table, bar chart, and validated query plan.
7. If GCP ADC is configured, repeat generation with Gemini planning enabled.
8. If Langfuse is configured, show the matching trace.

For the LMS submission, capture the generated-result area with the schema, request, success
metrics, and at least one table preview visible. Keep the screenshot below 10 MB and ensure any
certificate or identity field required by the course displays the correctly spelled name.

## Repository layout

```text
src/synthetic_data_ai/
  application/     use cases, prompts, validation, offline planners
  domain/          Pydantic schemas and generation/query plans
  infrastructure/  Vertex AI, SQLAlchemy, and Langfuse adapters
  ui/              Streamlit presentation layer
tests/              automated behavior and guardrail tests
examples/           sample PostgreSQL DDL
```

## Security notes

- `.env`, database files, virtual environments, caches, and credentials are ignored by Git.
- Never commit API keys, Langfuse secrets, or Google credential JSON files.
- Only schema names and planning prompts go to Gemini; deterministic code owns database writes.
- Only validated identifiers and allowlisted operations reach SQLAlchemy analytics.

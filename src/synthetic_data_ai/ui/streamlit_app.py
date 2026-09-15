"""Streamlit presentation layer for the complete application workflow."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from synthetic_data_ai.application.ddl_parser import DDLParseError, DDLParser
from synthetic_data_ai.application.generator import GenerationError, RelationalDataGenerator
from synthetic_data_ai.application.local_planner import build_local_generation_plan
from synthetic_data_ai.application.querying import build_local_query_plan
from synthetic_data_ai.config import Settings, get_settings
from synthetic_data_ai.domain.generation import GeneratedDataset, GenerationPlan
from synthetic_data_ai.domain.schema import RelationalSchema
from synthetic_data_ai.infrastructure.database import build_engine
from synthetic_data_ai.infrastructure.gemini import (
    GeminiPlanningError,
    GeminiQueryError,
    VertexGenerationPlanner,
    VertexQueryPlanner,
)
from synthetic_data_ai.infrastructure.relational_store import RelationalStore, TableSummary

DEFAULT_DDL = """CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    country VARCHAR(80) NOT NULL
);

CREATE TABLE employees (
    id UUID PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80) NOT NULL,
    email VARCHAR(180) NOT NULL UNIQUE,
    country VARCHAR(80) NOT NULL,
    salary NUMERIC(12, 2) NOT NULL,
    hired_at DATE NOT NULL,
    is_active BOOLEAN NOT NULL
);"""

DEFAULT_REQUEST = """Generate a European technology company.
Most employees should be located in Poland and Germany.
Use realistic salaries and five departments."""


def run() -> None:
    """Render the application without implementing domain rules in the UI."""

    settings = get_settings()
    st.set_page_config(page_title=settings.app_name, page_icon="🧬", layout="wide")
    _apply_styles()
    _render_sidebar(settings)

    st.title("Synthetic Data Studio")
    st.caption("Schema-aware relational data generation powered by Gemini and deterministic Python")

    generate_tab, explore_tab, chat_tab = st.tabs(
        ["Generate dataset", "Data explorer", "Talk to your data"]
    )
    with generate_tab:
        _render_generation(settings)
    with explore_tab:
        _render_explorer()
    with chat_tab:
        _render_data_chat(settings)


def _render_sidebar(settings: Settings) -> None:
    with st.sidebar:
        st.markdown("## Runtime")
        st.markdown(f"**GCP project**  \n`{settings.google_cloud_project}`")
        st.markdown(f"**Gemini model**  \n`{settings.gemini_model}`")
        st.markdown(f"**Database**  \n`{_database_label(settings.database_url)}`")
        st.markdown(
            f"**Langfuse tracing**  \n{'Enabled' if settings.langfuse_enabled else 'Optional'}"
        )
        st.divider()
        st.caption("Gemini plans. Python validates and generates. SQLAlchemy persists.")


def _render_generation(settings: Settings) -> None:
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown("### 1. Define the schema")
        ddl = st.text_area("PostgreSQL DDL", DEFAULT_DDL, height=305)
    with right:
        st.markdown("### 2. Describe the data")
        request = st.text_area("Generation request", DEFAULT_REQUEST, height=145)
        controls = st.columns(2)
        default_rows = controls[0].number_input(
            "Rows per main table", min_value=1, max_value=10_000, value=100
        )
        seed = controls[1].number_input("Seed", min_value=0, value=42)
        use_gemini = st.toggle(
            "Use Gemini planning through Vertex AI",
            value=False,
            help="Keep off for an offline demo; enable after gcloud ADC login.",
        )
        generate = st.button("Generate relational dataset", type="primary", width="stretch")

    if generate:
        _generate_dataset(
            settings,
            ddl,
            request,
            default_rows=int(default_rows),
            seed=int(seed),
            use_gemini=use_gemini,
        )

    dataset = st.session_state.get("dataset")
    summaries = st.session_state.get("summaries")
    if isinstance(dataset, GeneratedDataset) and isinstance(summaries, tuple):
        _render_generation_result(dataset, summaries)


def _generate_dataset(
    settings: Settings,
    ddl: str,
    request: str,
    *,
    default_rows: int,
    seed: int,
    use_gemini: bool,
) -> None:
    try:
        schema = DDLParser().parse(ddl)
        if use_gemini:
            plan = VertexGenerationPlanner(settings).create_plan(
                schema,
                request,
                default_rows=default_rows,
                seed=seed,
            )
            planning_mode = "Gemini structured plan"
        else:
            plan = build_local_generation_plan(
                schema,
                request,
                default_rows=default_rows,
                seed=seed,
            )
            planning_mode = "Deterministic offline plan"

        dataset = RelationalDataGenerator().generate(schema, plan)
        store = RelationalStore(build_engine(settings.database_url), schema)
        summaries = store.replace_dataset(dataset)
    except (DDLParseError, GenerationError, GeminiPlanningError, ValueError) as error:
        st.error(str(error))
        return

    st.session_state.update(
        schema=schema,
        plan=plan,
        dataset=dataset,
        store=store,
        summaries=summaries,
        planning_mode=planning_mode,
    )
    st.success("Dataset generated and saved with valid relational integrity.")


def _render_generation_result(
    dataset: GeneratedDataset,
    summaries: tuple[TableSummary, ...],
) -> None:
    st.markdown("### Generation result")
    metrics = st.columns(4)
    metrics[0].metric("Schema parsed", f"{len(dataset.tables)} tables")
    metrics[1].metric("Rows generated", f"{dataset.total_rows:,}")
    metrics[2].metric("Referential integrity", "Valid")
    metrics[3].metric("Saved to database", "Complete")

    plan = st.session_state.get("plan")
    if isinstance(plan, GenerationPlan):
        st.caption(
            f"{st.session_state.get('planning_mode', 'Validated plan')} · seed {plan.seed} · "
            f"{plan.intent_summary}"
        )

    for summary in summaries:
        with st.expander(f"{summary.name} · {summary.row_count:,} rows"):
            table = dataset.table(summary.name)
            st.dataframe(pd.DataFrame(table.rows[:20]), width="stretch", hide_index=True)


def _render_explorer() -> None:
    dataset = st.session_state.get("dataset")
    if not isinstance(dataset, GeneratedDataset):
        st.info("Generate a dataset first. Its tables will appear here for inspection and export.")
        return

    st.markdown("### Explore generated tables")
    table_name = st.selectbox("Table", [table.name for table in dataset.tables])
    generated_table = dataset.table(table_name)
    frame = pd.DataFrame(generated_table.rows)
    st.dataframe(frame, width="stretch", hide_index=True)
    st.download_button(
        "Download table as CSV",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=f"{table_name}.csv",
        mime="text/csv",
    )


def _render_data_chat(settings: Settings) -> None:
    schema = st.session_state.get("schema")
    store = st.session_state.get("store")
    if not isinstance(schema, RelationalSchema) or not isinstance(store, RelationalStore):
        st.info("Generate a dataset first, then ask questions about the saved data.")
        return

    st.markdown("### Ask a question")
    question = st.text_input(
        "Question",
        "What is the average salary by country in employees?",
    )
    use_gemini = st.toggle("Use Gemini to create the safe query plan", value=False)
    if st.button("Analyze data", type="primary"):
        try:
            if use_gemini:
                plan = VertexQueryPlanner(settings).create_plan(schema, question)
                mode = "Gemini query plan"
            else:
                plan = build_local_query_plan(schema, question)
                mode = "Offline query plan"
            result = store.execute_query(plan)
        except (GeminiQueryError, ValueError, KeyError) as error:
            st.error(str(error))
            return

        frame = pd.DataFrame(result.rows)
        st.success(f"{mode}: {plan.explanation or plan.operation.value}")
        st.dataframe(frame, width="stretch", hide_index=True)
        if list(frame.columns) == ["group", "value"] and not frame.empty:
            st.bar_chart(frame.set_index("group"), width="stretch")
        with st.expander("Validated query plan"):
            st.json(plan.model_dump(mode="json"))


def _database_label(database_url: str) -> str:
    return "PostgreSQL" if database_url.startswith("postgresql") else "SQLite (zero setup)"


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #f7f8fb; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stMetric"] {
            background: white;
            border: 1px solid #e7e9ef;
            border-radius: 14px;
            padding: 14px 16px;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(90deg, #5b4bdb, #6e62e5);
            border: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    run()

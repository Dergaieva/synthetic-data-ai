"""Streamlit presentation layer."""

import streamlit as st

from synthetic_data_ai.config import get_settings


def run() -> None:
    """Render the application shell without containing business logic."""

    settings = get_settings()
    st.set_page_config(page_title=settings.app_name, page_icon="🧬", layout="wide")

    st.title("🧬 Synthetic Data Studio")
    st.caption("Generate consistent relational datasets with deterministic rules and Gemini.")

    st.info(
        "Project foundation is ready. DDL parsing, generation, and data chat are added in the "
        "next implementation stages."
    )

    left, middle, right = st.columns(3)
    left.metric("Environment", settings.environment.title())
    middle.metric("Gemini model", settings.gemini_model)
    right.metric("Tracing", "Enabled" if settings.langfuse_enabled else "Optional")


if __name__ == "__main__":
    run()

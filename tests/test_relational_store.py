"""Relational persistence tests."""

from synthetic_data_ai.application.ddl_parser import DDLParser
from synthetic_data_ai.application.generator import RelationalDataGenerator
from synthetic_data_ai.domain.generation import GenerationPlan
from synthetic_data_ai.infrastructure.database import build_engine
from synthetic_data_ai.infrastructure.relational_store import RelationalStore

DDL = """
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE
);
CREATE TABLE employees (
    id UUID PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    email VARCHAR(180) NOT NULL UNIQUE
);
"""


def test_store_replaces_counts_and_previews_dataset() -> None:
    schema = DDLParser().parse(DDL)
    plan = GenerationPlan(seed=42, default_rows=7, table_rows={"departments": 3})
    dataset = RelationalDataGenerator().generate(schema, plan)
    store = RelationalStore(build_engine("sqlite+pysqlite:///:memory:"), schema)

    first_summaries = store.replace_dataset(dataset)
    second_summaries = store.replace_dataset(dataset)

    assert [(item.name, item.row_count) for item in first_summaries] == [
        ("departments", 3),
        ("employees", 7),
    ]
    assert second_summaries == first_summaries
    assert len(store.preview("employees", limit=2)) == 2


def test_store_rejects_unknown_preview_table() -> None:
    schema = DDLParser().parse(DDL)
    store = RelationalStore(build_engine("sqlite+pysqlite:///:memory:"), schema)

    try:
        store.preview("not_a_table")
    except KeyError as error:
        assert "Unknown managed table" in str(error)
    else:
        raise AssertionError("Expected an unknown table error")

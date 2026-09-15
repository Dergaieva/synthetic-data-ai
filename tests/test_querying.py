"""Safe analytical query tests."""

from synthetic_data_ai.application.ddl_parser import DDLParser
from synthetic_data_ai.application.generator import RelationalDataGenerator
from synthetic_data_ai.application.querying import (
    build_local_query_plan,
    validate_query_plan,
)
from synthetic_data_ai.domain.generation import GenerationPlan
from synthetic_data_ai.domain.query import QueryOperation, QueryPlan
from synthetic_data_ai.infrastructure.database import build_engine
from synthetic_data_ai.infrastructure.relational_store import RelationalStore

DDL = """
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    country VARCHAR(80) NOT NULL,
    salary NUMERIC(12, 2) NOT NULL
);
"""


def test_group_average_query_uses_allowlisted_plan() -> None:
    schema = DDLParser().parse(DDL)
    dataset = RelationalDataGenerator().generate(schema, GenerationPlan(default_rows=20))
    store = RelationalStore(build_engine("sqlite+pysqlite:///:memory:"), schema)
    store.replace_dataset(dataset)
    query = QueryPlan(
        table="employees",
        operation=QueryOperation.GROUP_AVERAGE,
        metric_column="salary",
        group_by_column="country",
    )

    result = store.execute_query(validate_query_plan(schema, query))

    assert result.rows
    assert set(result.rows[0]) == {"group", "value"}


def test_local_query_plan_understands_average_by_country() -> None:
    schema = DDLParser().parse(DDL)

    plan = build_local_query_plan(schema, "What is the average salary by country?")

    assert plan.operation is QueryOperation.GROUP_AVERAGE
    assert plan.metric_column == "salary"
    assert plan.group_by_column == "country"

"""Vertex AI generation planner tests using a fake SDK client."""

from types import SimpleNamespace
from typing import Any

import pytest

from synthetic_data_ai.application.ddl_parser import DDLParser
from synthetic_data_ai.config import Settings
from synthetic_data_ai.domain.generation import ColumnRule, GenerationPlan, RuleKind
from synthetic_data_ai.infrastructure.gemini import GeminiPlanningError, VertexGenerationPlanner

DDL = """
CREATE TABLE departments (id INTEGER PRIMARY KEY, name VARCHAR(80) NOT NULL);
CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    department_id INTEGER REFERENCES departments(id),
    country VARCHAR(80) NOT NULL,
    salary NUMERIC(12, 2) NOT NULL
);
"""


class FakeModels:
    def __init__(self, parsed: object) -> None:
        self.parsed = parsed
        self.last_request: dict[str, Any] | None = None

    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        self.last_request = kwargs
        return SimpleNamespace(parsed=self.parsed, text=None)


class FakeClient:
    def __init__(self, parsed: object) -> None:
        self.models = FakeModels(parsed)


def test_planner_requests_and_returns_structured_plan() -> None:
    schema = DDLParser().parse(DDL)
    expected = GenerationPlan(
        seed=5,
        default_rows=20,
        table_rows={"departments": 4, "employees": 20},
        column_rules={
            "employees": {
                "country": ColumnRule(
                    kind=RuleKind.CHOICE,
                    choices=("Poland", "Germany"),
                )
            }
        },
        intent_summary="European technology company",
    )
    client = FakeClient(expected)
    planner = VertexGenerationPlanner(Settings(_env_file=None), client=client)

    actual = planner.create_plan(
        schema,
        "Most employees should be in Poland and Germany",
        default_rows=20,
        seed=5,
    )

    assert actual == expected
    assert client.models.last_request is not None
    assert client.models.last_request["model"] == "gemini-2.5-flash"
    assert "Never create SQL" in client.models.last_request["contents"]


def test_planner_rejects_key_column_overrides() -> None:
    schema = DDLParser().parse(DDL)
    invalid = GenerationPlan(
        column_rules={"employees": {"department_id": ColumnRule(kind=RuleKind.CONSTANT, value=999)}}
    )
    planner = VertexGenerationPlanner(Settings(_env_file=None), client=FakeClient(invalid))

    with pytest.raises(GeminiPlanningError, match="key column"):
        planner.create_plan(schema, "Break the foreign key", default_rows=10, seed=42)

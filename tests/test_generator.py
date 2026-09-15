"""Deterministic relational generation tests."""

from synthetic_data_ai.application.ddl_parser import DDLParser
from synthetic_data_ai.application.generator import RelationalDataGenerator
from synthetic_data_ai.domain.generation import GenerationPlan

DDL = """
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    department_name VARCHAR(80) NOT NULL UNIQUE
);
CREATE TABLE employees (
    id UUID PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    email VARCHAR(180) NOT NULL UNIQUE,
    salary NUMERIC(12, 2) NOT NULL,
    hired_at DATE NOT NULL
);
"""


def test_generation_is_reproducible_and_preserves_foreign_keys() -> None:
    schema = DDLParser().parse(DDL)
    plan = GenerationPlan(seed=7, default_rows=10, table_rows={"departments": 5})
    generator = RelationalDataGenerator()

    first = generator.generate(schema, plan)
    second = generator.generate(schema, plan)

    assert first == second
    assert first.total_rows == 15

    department_ids = {row["id"] for row in first.table("departments").rows}
    employee_department_ids = {row["department_id"] for row in first.table("employees").rows}
    assert employee_department_ids <= department_ids


def test_generation_produces_unique_emails_and_primary_keys() -> None:
    schema = DDLParser().parse(DDL)
    dataset = RelationalDataGenerator().generate(
        schema,
        GenerationPlan(seed=42, default_rows=30, table_rows={"departments": 5}),
    )

    employee_rows = dataset.table("employees").rows
    assert len({row["id"] for row in employee_rows}) == len(employee_rows)
    assert len({row["email"] for row in employee_rows}) == len(employee_rows)

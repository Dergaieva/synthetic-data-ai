"""DDL parser tests."""

import pytest

from synthetic_data_ai.application.ddl_parser import DDLParseError, DDLParser
from synthetic_data_ai.domain.schema import DataCategory

COMPANY_DDL = """
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE employees (
    id UUID PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(id),
    email VARCHAR(180) NOT NULL UNIQUE,
    salary NUMERIC(12, 2),
    hired_at DATE NOT NULL
);
"""


def test_parser_builds_typed_schema_and_relationships() -> None:
    schema = DDLParser().parse(COMPANY_DDL)

    assert schema.generation_order() == ("departments", "employees")
    assert schema.table("employees").column("salary").category is DataCategory.DECIMAL
    assert schema.table("employees").column("salary").scale == 2
    assert schema.table("employees").column("email").nullable is False
    assert schema.table("employees").foreign_keys[0].referenced_table == "departments"


def test_parser_supports_named_table_foreign_key() -> None:
    ddl = """
    CREATE TABLE parents (id INTEGER PRIMARY KEY);
    CREATE TABLE children (
        id INTEGER PRIMARY KEY,
        parent_id INTEGER NOT NULL,
        CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES parents(id)
    );
    """

    schema = DDLParser().parse(ddl)

    assert schema.table("children").foreign_keys[0].local_column == "parent_id"


@pytest.mark.parametrize("ddl", ["", "SELECT 1", "CREATE VIEW example AS SELECT 1"])
def test_parser_rejects_unsupported_input(ddl: str) -> None:
    with pytest.raises(DDLParseError):
        DDLParser().parse(ddl)


def test_parser_rejects_circular_dependencies() -> None:
    ddl = """
    CREATE TABLE first_table (
        id INTEGER PRIMARY KEY,
        second_id INTEGER REFERENCES second_table(id)
    );
    CREATE TABLE second_table (
        id INTEGER PRIMARY KEY,
        first_id INTEGER REFERENCES first_table(id)
    );
    """

    with pytest.raises(DDLParseError, match="Circular"):
        DDLParser().parse(ddl)

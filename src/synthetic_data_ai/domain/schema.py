"""Typed relational-schema models."""

from __future__ import annotations

from collections import deque
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataCategory(StrEnum):
    """Portable categories used by the deterministic generator."""

    INTEGER = "integer"
    DECIMAL = "decimal"
    STRING = "string"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    JSON = "json"


class ColumnDefinition(BaseModel):
    """A database column relevant to synthetic-data generation."""

    model_config = ConfigDict(frozen=True)

    name: str
    sql_type: str
    category: DataCategory
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    default_sql: str | None = None
    max_length: int | None = None
    precision: int | None = None
    scale: int | None = None


class ForeignKeyDefinition(BaseModel):
    """A supported single-column foreign-key relationship."""

    model_config = ConfigDict(frozen=True)

    local_column: str
    referenced_table: str
    referenced_column: str


class TableDefinition(BaseModel):
    """A relational table and its generation-relevant constraints."""

    model_config = ConfigDict(frozen=True)

    name: str
    columns: tuple[ColumnDefinition, ...]
    foreign_keys: tuple[ForeignKeyDefinition, ...] = ()

    @model_validator(mode="after")
    def validate_columns_and_keys(self) -> TableDefinition:
        names = [column.name for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError(f"Table {self.name!r} contains duplicate column names")

        known = set(names)
        for foreign_key in self.foreign_keys:
            if foreign_key.local_column not in known:
                raise ValueError(
                    f"Foreign key uses unknown column {self.name}.{foreign_key.local_column}"
                )
        return self

    def column(self, name: str) -> ColumnDefinition:
        """Return a column by name or raise a readable error."""

        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"Unknown column {self.name}.{name}")


class RelationalSchema(BaseModel):
    """A validated set of related database tables."""

    model_config = ConfigDict(frozen=True)

    tables: tuple[TableDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> RelationalSchema:
        tables = {table.name: table for table in self.tables}
        if len(tables) != len(self.tables):
            raise ValueError("Schema contains duplicate table names")

        for table in self.tables:
            for foreign_key in table.foreign_keys:
                target = tables.get(foreign_key.referenced_table)
                if target is None:
                    raise ValueError(
                        f"Foreign key references unknown table {foreign_key.referenced_table!r}"
                    )
                try:
                    target.column(foreign_key.referenced_column)
                except KeyError as error:
                    raise ValueError(str(error)) from error
        return self

    def table(self, name: str) -> TableDefinition:
        """Return a table by name or raise a readable error."""

        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(f"Unknown table {name}")

    def generation_order(self) -> tuple[str, ...]:
        """Return parent tables before dependent tables using a topological sort."""

        dependencies: dict[str, set[str]] = {
            table.name: {
                key.referenced_table
                for key in table.foreign_keys
                if key.referenced_table != table.name
            }
            for table in self.tables
        }
        ready = deque(sorted(name for name, deps in dependencies.items() if not deps))
        ordered: list[str] = []

        while ready:
            current = ready.popleft()
            ordered.append(current)
            for name in sorted(dependencies):
                if current in dependencies[name]:
                    dependencies[name].remove(current)
                    if not dependencies[name] and name not in ordered and name not in ready:
                        ready.append(name)

        if len(ordered) != len(dependencies):
            cyclic = sorted(name for name, deps in dependencies.items() if deps)
            raise ValueError(f"Circular foreign-key dependency: {', '.join(cyclic)}")
        return tuple(ordered)

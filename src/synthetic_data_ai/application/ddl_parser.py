"""Parse a safe subset of PostgreSQL DDL into domain models."""

from __future__ import annotations

from collections.abc import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from synthetic_data_ai.domain.schema import (
    ColumnDefinition,
    DataCategory,
    ForeignKeyDefinition,
    RelationalSchema,
    TableDefinition,
)


class DDLParseError(ValueError):
    """Raised when uploaded DDL is invalid or outside the supported subset."""


class DDLParser:
    """Translate PostgreSQL CREATE TABLE statements into validated domain models."""

    def parse(self, ddl: str) -> RelationalSchema:
        """Parse one or more CREATE TABLE statements."""

        if not ddl.strip():
            raise DDLParseError("DDL cannot be empty")

        try:
            statements = sqlglot.parse(ddl, read="postgres")
        except ParseError as error:
            raise DDLParseError(f"Invalid SQL DDL: {error}") from error

        tables: list[TableDefinition] = []
        for statement in statements:
            if not isinstance(statement, exp.Create) or statement.args.get("kind") != "TABLE":
                raise DDLParseError("Only CREATE TABLE statements are supported")
            tables.append(self._parse_table(statement))

        try:
            schema = RelationalSchema(tables=tuple(tables))
            schema.generation_order()
        except ValueError as error:
            raise DDLParseError(str(error)) from error
        return schema

    def _parse_table(self, create: exp.Create) -> TableDefinition:
        schema_expression = create.this
        if not isinstance(schema_expression, exp.Schema) or not isinstance(
            schema_expression.this, exp.Table
        ):
            raise DDLParseError("CREATE TABLE must include an explicit column list")

        table_name = schema_expression.this.name
        columns = [
            self._parse_column(item)
            for item in schema_expression.expressions
            if isinstance(item, exp.ColumnDef)
        ]
        if not columns:
            raise DDLParseError(f"Table {table_name!r} has no columns")

        table_primary_keys = {
            identifier.name
            for item in schema_expression.expressions
            if isinstance(item, exp.PrimaryKey)
            for identifier in item.expressions
            if isinstance(identifier, exp.Identifier)
        }
        if table_primary_keys:
            columns = [
                column.model_copy(
                    update={"primary_key": True, "nullable": False},
                )
                if column.name in table_primary_keys
                else column
                for column in columns
            ]

        foreign_keys: list[ForeignKeyDefinition] = []
        for item in schema_expression.expressions:
            if isinstance(item, exp.ColumnDef):
                foreign_keys.extend(self._inline_foreign_keys(item))
            elif isinstance(item, exp.ForeignKey):
                foreign_keys.append(self._parse_table_foreign_key(item))
            elif isinstance(item, exp.Constraint):
                for expression in item.expressions:
                    if isinstance(expression, exp.ForeignKey):
                        foreign_keys.append(self._parse_table_foreign_key(expression))

        return TableDefinition(
            name=table_name,
            columns=tuple(columns),
            foreign_keys=tuple(foreign_keys),
        )

    def _parse_column(self, definition: exp.ColumnDef) -> ColumnDefinition:
        data_type = definition.args.get("kind")
        if not isinstance(data_type, exp.DataType):
            raise DDLParseError(f"Column {definition.name!r} has no supported data type")

        constraint_kinds = [
            constraint.args.get("kind")
            for constraint in definition.constraints
            if isinstance(constraint, exp.ColumnConstraint)
        ]
        primary_key = any(
            isinstance(kind, exp.PrimaryKeyColumnConstraint) for kind in constraint_kinds
        )
        nullable = not primary_key and not any(
            isinstance(kind, exp.NotNullColumnConstraint) for kind in constraint_kinds
        )
        unique = primary_key or any(
            isinstance(kind, exp.UniqueColumnConstraint) for kind in constraint_kinds
        )
        default = next(
            (
                kind.this.sql(dialect="postgres")
                for kind in constraint_kinds
                if isinstance(kind, exp.DefaultColumnConstraint)
                and isinstance(kind.this, exp.Expression)
            ),
            None,
        )
        parameters = self._integer_parameters(data_type.expressions)
        category = self._category(data_type)

        return ColumnDefinition(
            name=definition.name,
            sql_type=data_type.sql(dialect="postgres"),
            category=category,
            nullable=nullable,
            primary_key=primary_key,
            unique=unique,
            default_sql=default,
            max_length=parameters[0] if category is DataCategory.STRING and parameters else None,
            precision=parameters[0] if category is DataCategory.DECIMAL and parameters else None,
            scale=parameters[1]
            if category is DataCategory.DECIMAL and len(parameters) > 1
            else None,
        )

    def _inline_foreign_keys(self, definition: exp.ColumnDef) -> Iterable[ForeignKeyDefinition]:
        for constraint in definition.constraints:
            kind = constraint.args.get("kind")
            if isinstance(kind, exp.Reference):
                table, column = self._reference_target(kind)
                yield ForeignKeyDefinition(
                    local_column=definition.name,
                    referenced_table=table,
                    referenced_column=column,
                )

    def _parse_table_foreign_key(self, foreign_key: exp.ForeignKey) -> ForeignKeyDefinition:
        local_columns = [
            identifier.name
            for identifier in foreign_key.expressions
            if isinstance(identifier, exp.Identifier)
        ]
        reference = foreign_key.args.get("reference")
        if len(local_columns) != 1 or not isinstance(reference, exp.Reference):
            raise DDLParseError("Only single-column foreign keys are supported")
        table, column = self._reference_target(reference)
        return ForeignKeyDefinition(
            local_column=local_columns[0],
            referenced_table=table,
            referenced_column=column,
        )

    def _reference_target(self, reference: exp.Reference) -> tuple[str, str]:
        target = reference.this
        if not isinstance(target, exp.Schema) or not isinstance(target.this, exp.Table):
            raise DDLParseError("Foreign key must reference a table and column")
        columns = [
            identifier.name
            for identifier in target.expressions
            if isinstance(identifier, exp.Identifier)
        ]
        if len(columns) != 1:
            raise DDLParseError("Only single-column foreign keys are supported")
        return target.this.name, columns[0]

    def _category(self, data_type: exp.DataType) -> DataCategory:
        raw = data_type.this.value.upper()
        categories = {
            DataCategory.INTEGER: {
                "TINYINT",
                "SMALLINT",
                "INT",
                "BIGINT",
                "UTINYINT",
                "USMALLINT",
                "UINT",
                "UBIGINT",
                "SERIAL",
                "SMALLSERIAL",
                "BIGSERIAL",
            },
            DataCategory.DECIMAL: {
                "DECIMAL",
                "NUMERIC",
                "FLOAT",
                "DOUBLE",
                "REAL",
                "MONEY",
            },
            DataCategory.STRING: {
                "CHAR",
                "NCHAR",
                "VARCHAR",
                "NVARCHAR",
                "TEXT",
                "UUIDTEXT",
                "ENUM",
            },
            DataCategory.BOOLEAN: {"BOOLEAN"},
            DataCategory.DATE: {"DATE"},
            DataCategory.DATETIME: {
                "DATETIME",
                "DATETIME2",
                "TIMESTAMP",
                "TIMESTAMPTZ",
                "TIME",
                "TIMETZ",
            },
            DataCategory.UUID: {"UUID"},
            DataCategory.JSON: {"JSON", "JSONB"},
        }
        for category, names in categories.items():
            if raw in names:
                return category
        raise DDLParseError(f"Unsupported SQL type: {data_type.sql(dialect='postgres')}")

    def _integer_parameters(self, parameters: list[exp.Expression]) -> tuple[int, ...]:
        values: list[int] = []
        for parameter in parameters:
            literal = parameter.find(exp.Literal)
            if literal is not None and not literal.is_string:
                values.append(int(literal.this))
        return tuple(values)

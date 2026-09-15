"""Safe SQLAlchemy persistence for generated relational datasets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Uuid,
    func,
    select,
)
from sqlalchemy.sql.type_api import TypeEngine

from synthetic_data_ai.domain.generation import GeneratedDataset
from synthetic_data_ai.domain.query import QueryOperation, QueryPlan, QueryResult
from synthetic_data_ai.domain.schema import (
    ColumnDefinition,
    DataCategory,
    RelationalSchema,
)


class TableSummary(BaseModel):
    """Display-safe persistence result for one table."""

    model_config = ConfigDict(frozen=True)

    name: str
    row_count: int


class RelationalStore:
    """Materialize and query one validated relational schema."""

    def __init__(self, engine: Engine, schema: RelationalSchema) -> None:
        self._engine = engine
        self._schema = schema
        self._metadata = MetaData()
        self._tables = self._build_tables(schema)

    def replace_dataset(self, dataset: GeneratedDataset) -> tuple[TableSummary, ...]:
        """Atomically replace managed tables with the supplied generated rows."""

        expected = set(self._tables)
        actual = {table.name for table in dataset.tables}
        if actual != expected:
            raise ValueError(
                "Dataset tables do not match schema: "
                f"expected {sorted(expected)}, got {sorted(actual)}"
            )

        with self._engine.begin() as connection:
            self._metadata.drop_all(connection, checkfirst=True)
            self._metadata.create_all(connection)
            for table_name in self._schema.generation_order():
                generated_table = dataset.table(table_name)
                if generated_table.rows:
                    connection.execute(
                        self._tables[table_name].insert(),
                        [dict(row) for row in generated_table.rows],
                    )
        return self.table_summaries()

    def table_summaries(self) -> tuple[TableSummary, ...]:
        """Return row counts without accepting user-authored SQL."""

        summaries: list[TableSummary] = []
        with self._engine.connect() as connection:
            for table_name in self._schema.generation_order():
                table = self._tables[table_name]
                count = connection.scalar(select(func.count()).select_from(table))
                summaries.append(TableSummary(name=table_name, row_count=int(count or 0)))
        return tuple(summaries)

    def preview(self, table_name: str, limit: int = 20) -> tuple[dict[str, object], ...]:
        """Return a bounded table preview selected through SQLAlchemy expressions."""

        table = self._tables.get(table_name)
        if table is None:
            raise KeyError(f"Unknown managed table {table_name}")
        safe_limit = min(max(limit, 1), 100)
        with self._engine.connect() as connection:
            rows = connection.execute(select(table).limit(safe_limit)).mappings()
            return tuple(dict(row) for row in rows)

    def execute_query(self, plan: QueryPlan) -> QueryResult:
        """Translate an allowlisted QueryPlan into SQLAlchemy expressions."""

        table = self._tables.get(plan.table)
        if table is None:
            raise KeyError(f"Unknown managed table {plan.table}")
        if plan.operation is QueryOperation.PREVIEW:
            return QueryResult(plan=plan, rows=self.preview(plan.table, plan.limit))

        metric = table.c[plan.metric_column] if plan.metric_column else None
        group = table.c[plan.group_by_column] if plan.group_by_column else None
        if plan.operation is QueryOperation.COUNT:
            statement = select(func.count().label("value")).select_from(table)
        elif plan.operation is QueryOperation.AVERAGE and metric is not None:
            statement = select(func.avg(metric).label("value"))
        elif plan.operation is QueryOperation.SUM and metric is not None:
            statement = select(func.sum(metric).label("value"))
        elif plan.operation is QueryOperation.MINIMUM and metric is not None:
            statement = select(func.min(metric).label("value"))
        elif plan.operation is QueryOperation.MAXIMUM and metric is not None:
            statement = select(func.max(metric).label("value"))
        elif plan.operation is QueryOperation.GROUP_COUNT and group is not None:
            statement = (
                select(group.label("group"), func.count().label("value"))
                .group_by(group)
                .order_by(func.count().desc())
                .limit(plan.limit)
            )
        elif (
            plan.operation is QueryOperation.GROUP_AVERAGE
            and group is not None
            and metric is not None
        ):
            statement = (
                select(group.label("group"), func.avg(metric).label("value"))
                .group_by(group)
                .order_by(func.avg(metric).desc())
                .limit(plan.limit)
            )
        else:
            raise ValueError(f"Incomplete query plan for {plan.operation}")

        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings()
            return QueryResult(plan=plan, rows=tuple(dict(row) for row in rows))

    def _build_tables(self, schema: RelationalSchema) -> Mapping[str, Table]:
        tables: dict[str, Table] = {}
        for definition in schema.tables:
            foreign_keys = {key.local_column: key for key in definition.foreign_keys}
            columns: list[Column[Any]] = []
            for column in definition.columns:
                sql_type = self._sqlalchemy_type(column)
                foreign_key = foreign_keys.get(column.name)
                if foreign_key is not None:
                    built_column = Column(
                        column.name,
                        sql_type,
                        ForeignKey(
                            f"{foreign_key.referenced_table}.{foreign_key.referenced_column}"
                        ),
                        primary_key=column.primary_key,
                        nullable=column.nullable,
                        unique=column.unique and not column.primary_key,
                    )
                else:
                    built_column = Column(
                        column.name,
                        sql_type,
                        primary_key=column.primary_key,
                        nullable=column.nullable,
                        unique=column.unique and not column.primary_key,
                    )
                columns.append(built_column)
            tables[definition.name] = Table(definition.name, self._metadata, *columns)
        return tables

    def _sqlalchemy_type(self, column: ColumnDefinition) -> TypeEngine[Any]:
        if column.category is DataCategory.INTEGER:
            return Integer()
        if column.category is DataCategory.DECIMAL:
            return Numeric(precision=column.precision, scale=column.scale)
        if column.category is DataCategory.STRING:
            return String(length=column.max_length)
        if column.category is DataCategory.BOOLEAN:
            return Boolean()
        if column.category is DataCategory.DATE:
            return Date()
        if column.category is DataCategory.DATETIME:
            return DateTime(timezone=True)
        if column.category is DataCategory.UUID:
            return Uuid(as_uuid=False)
        if column.category is DataCategory.JSON:
            return JSON()
        raise ValueError(f"Unsupported data category: {column.category}")

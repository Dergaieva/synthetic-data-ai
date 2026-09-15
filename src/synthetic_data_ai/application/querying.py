"""Query-plan prompting, validation, and offline planning."""

from __future__ import annotations

from synthetic_data_ai.domain.query import QueryOperation, QueryPlan
from synthetic_data_ai.domain.schema import DataCategory, RelationalSchema


class QueryPlanValidationError(ValueError):
    """Raised when a query plan targets invalid schema elements."""


def build_query_prompt(schema: RelationalSchema, question: str) -> str:
    """Build instructions for Gemini to return an allowlisted QueryPlan."""

    return f"""
Translate the user's analytical question into the supplied QueryPlan response schema.

Rules:
- Never return SQL.
- Use only existing table and column names from the relational schema.
- Use one allowlisted operation: preview, count, average, sum, minimum, maximum,
  group_count, group_average.
- Choose a numeric metric column for average, sum, minimum, maximum, or group_average.
- Keep limit at or below 100.

Relational schema:
{schema.model_dump_json(indent=2)}

Question:
{question.strip()}
""".strip()


def validate_query_plan(schema: RelationalSchema, plan: QueryPlan) -> QueryPlan:
    """Validate all identifiers and numeric-operation constraints."""

    try:
        table = schema.table(plan.table)
    except KeyError as error:
        raise QueryPlanValidationError(str(error)) from error

    for name in (plan.metric_column, plan.group_by_column):
        if name is not None:
            try:
                table.column(name)
            except KeyError as error:
                raise QueryPlanValidationError(str(error)) from error

    if plan.metric_column is not None and plan.operation in {
        QueryOperation.AVERAGE,
        QueryOperation.SUM,
        QueryOperation.GROUP_AVERAGE,
    }:
        metric = table.column(plan.metric_column)
        if metric.category not in {DataCategory.INTEGER, DataCategory.DECIMAL}:
            raise QueryPlanValidationError(
                f"Operation {plan.operation} requires a numeric metric column"
            )
    return plan


def build_local_query_plan(schema: RelationalSchema, question: str) -> QueryPlan:
    """Create a useful offline plan for common demo questions."""

    lowered = question.lower()
    table = next(
        (candidate for candidate in schema.tables if candidate.name.lower() in lowered),
        schema.tables[-1],
    )
    numeric = next(
        (
            column
            for column in table.columns
            if column.category in {DataCategory.INTEGER, DataCategory.DECIMAL}
            and not column.primary_key
        ),
        None,
    )
    named_metric = next(
        (
            column
            for column in table.columns
            if column.category in {DataCategory.INTEGER, DataCategory.DECIMAL}
            and not column.primary_key
            and column.name.lower() in lowered
        ),
        numeric,
    )
    group = next(
        (
            column
            for column in table.columns
            if column.name.lower() in lowered and column is not named_metric
        ),
        None,
    )
    if group is None:
        group = next(
            (
                column
                for column in table.columns
                if column.name.lower() in {"country", "status", "department_name"}
            ),
            None,
        )

    wants_average = any(token in lowered for token in ("average", "avg", "mean"))
    wants_group = any(token in lowered for token in (" by ", "each", "per "))
    if wants_average and named_metric is not None and wants_group and group is not None:
        operation = QueryOperation.GROUP_AVERAGE
    elif wants_average and named_metric is not None:
        operation = QueryOperation.AVERAGE
    elif wants_group and group is not None:
        operation = QueryOperation.GROUP_COUNT
    elif "count" in lowered or "how many" in lowered:
        operation = QueryOperation.COUNT
    else:
        operation = QueryOperation.PREVIEW

    return validate_query_plan(
        schema,
        QueryPlan(
            table=table.name,
            operation=operation,
            metric_column=named_metric.name
            if operation in {QueryOperation.AVERAGE, QueryOperation.GROUP_AVERAGE}
            and named_metric is not None
            else None,
            group_by_column=group.name
            if operation in {QueryOperation.GROUP_COUNT, QueryOperation.GROUP_AVERAGE}
            and group is not None
            else None,
            explanation="Safe local query plan",
        ),
    )

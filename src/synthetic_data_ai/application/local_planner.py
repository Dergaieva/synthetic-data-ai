"""Offline generation plan used for fast demos and deterministic tests."""

from __future__ import annotations

from synthetic_data_ai.domain.generation import ColumnRule, GenerationPlan, RuleKind
from synthetic_data_ai.domain.schema import DataCategory, RelationalSchema


def build_local_generation_plan(
    schema: RelationalSchema,
    user_request: str,
    *,
    default_rows: int,
    seed: int,
) -> GenerationPlan:
    """Infer a conservative plan without a network call."""

    lowered = user_request.lower()
    rules: dict[str, dict[str, ColumnRule]] = {}
    table_rows: dict[str, int] = {}

    for table in schema.tables:
        table_rules: dict[str, ColumnRule] = {}
        if table.name.lower() in {"departments", "department"}:
            table_rows[table.name] = min(default_rows, 5)
        for column in table.columns:
            if column.primary_key or any(
                key.local_column == column.name for key in table.foreign_keys
            ):
                continue
            name = column.name.lower()
            if "country" in name and any(
                country in lowered for country in ("poland", "germany", "europe")
            ):
                table_rules[column.name] = ColumnRule(
                    kind=RuleKind.CHOICE,
                    choices=("Poland", "Germany", "Netherlands", "Austria"),
                )
            elif "department" in name or (name == "name" and "department" in table.name.lower()):
                table_rules[column.name] = ColumnRule(
                    kind=RuleKind.CHOICE,
                    choices=("Engineering", "Product", "Finance", "People", "Sales"),
                )
            elif "salary" in name and column.category is DataCategory.DECIMAL:
                table_rules[column.name] = ColumnRule(
                    kind=RuleKind.DECIMAL_RANGE,
                    minimum=55_000,
                    maximum=165_000,
                )
        if table_rules:
            rules[table.name] = table_rules

    return GenerationPlan(
        seed=seed,
        default_rows=default_rows,
        table_rows=table_rows,
        column_rules=rules,
        locale="en_US",
        intent_summary=user_request.strip() or "Realistic synthetic relational data",
    )

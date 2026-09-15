"""Build and validate prompts and plans without depending on a specific LLM SDK."""

from __future__ import annotations

from synthetic_data_ai.domain.generation import GenerationPlan
from synthetic_data_ai.domain.schema import RelationalSchema


class PlanValidationError(ValueError):
    """Raised when an LLM plan targets schema elements it may not control."""


def build_planning_prompt(
    schema: RelationalSchema,
    user_request: str,
    *,
    default_rows: int,
    seed: int,
) -> str:
    """Build a bounded prompt for structured plan generation."""

    request = user_request.strip() or "Generate realistic synthetic business data."
    return f"""
You are planning synthetic data generation for a relational database.
Return only a GenerationPlan that follows the supplied response schema.

Rules:
- Keep all table and column names exactly as provided.
- Never create SQL and never propose schema changes.
- Do not add rules for primary-key or foreign-key columns.
- Use only: auto, choice, integer_range, decimal_range, constant.
- Keep row counts between 1 and 10,000.
- Prefer a low null_probability unless the user explicitly requests missing data.
- Use locale en_US unless another locale is clearly requested.

Default rows: {default_rows}
Seed: {seed}

Relational schema:
{schema.model_dump_json(indent=2)}

User request:
{request}
""".strip()


def validate_plan_for_schema(
    schema: RelationalSchema,
    plan: GenerationPlan,
) -> GenerationPlan:
    """Reject unknown targets and key-column overrides before generation."""

    known_tables = {table.name for table in schema.tables}
    unknown_row_tables = sorted(set(plan.table_rows) - known_tables)
    unknown_rule_tables = sorted(set(plan.column_rules) - known_tables)
    if unknown_row_tables or unknown_rule_tables:
        unknown = sorted(set(unknown_row_tables + unknown_rule_tables))
        raise PlanValidationError(f"Plan references unknown tables: {', '.join(unknown)}")

    for table_name, rules in plan.column_rules.items():
        table = schema.table(table_name)
        foreign_keys = {key.local_column for key in table.foreign_keys}
        for column_name in rules:
            try:
                column = table.column(column_name)
            except KeyError as error:
                raise PlanValidationError(str(error)) from error
            if column.primary_key or column.name in foreign_keys:
                raise PlanValidationError(
                    f"Plan cannot override key column {table_name}.{column_name}"
                )
    return plan

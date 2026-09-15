"""Generation plan and generated dataset models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

type RuleValue = str | int | float | bool


class RuleKind(StrEnum):
    """Small allowlist of generation strategies an LLM may request."""

    AUTO = "auto"
    CHOICE = "choice"
    INTEGER_RANGE = "integer_range"
    DECIMAL_RANGE = "decimal_range"
    CONSTANT = "constant"


class ColumnRule(BaseModel):
    """Validated hint applied by the deterministic generator."""

    model_config = ConfigDict(frozen=True)

    kind: RuleKind = RuleKind.AUTO
    choices: tuple[RuleValue, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    value: RuleValue | None = None

    @model_validator(mode="after")
    def validate_strategy_parameters(self) -> ColumnRule:
        if self.kind is RuleKind.CHOICE and not self.choices:
            raise ValueError("Choice rules require at least one value")
        if self.kind in {RuleKind.INTEGER_RANGE, RuleKind.DECIMAL_RANGE}:
            if self.minimum is None or self.maximum is None:
                raise ValueError("Range rules require minimum and maximum")
            if self.minimum > self.maximum:
                raise ValueError("Range rule minimum cannot exceed maximum")
        if self.kind is RuleKind.CONSTANT and self.value is None:
            raise ValueError("Constant rules require a value")
        return self


class GenerationPlan(BaseModel):
    """Validated user/LLM intent consumed by deterministic Python code."""

    model_config = ConfigDict(frozen=True)

    seed: int = 42
    default_rows: int = Field(default=25, ge=1, le=10_000)
    table_rows: dict[str, int] = Field(default_factory=dict)
    column_rules: dict[str, dict[str, ColumnRule]] = Field(default_factory=dict)
    locale: str = "en_US"
    null_probability: float = Field(default=0.05, ge=0, le=0.5)
    intent_summary: str = "Generate realistic synthetic data"

    def rows_for(self, table_name: str) -> int:
        """Return a table override or the plan-wide default."""

        return self.table_rows.get(table_name, self.default_rows)

    def rule_for(self, table_name: str, column_name: str) -> ColumnRule:
        """Return a configured rule or the default automatic strategy."""

        return self.column_rules.get(table_name, {}).get(column_name, ColumnRule())


class GeneratedTable(BaseModel):
    """Generated rows for a single table."""

    model_config = ConfigDict(frozen=True)

    name: str
    rows: tuple[dict[str, object], ...]


class GeneratedDataset(BaseModel):
    """Complete generated data plus metadata for UI and persistence."""

    model_config = ConfigDict(frozen=True)

    seed: int
    tables: tuple[GeneratedTable, ...]

    @property
    def total_rows(self) -> int:
        """Return the total number of generated records."""

        return sum(len(table.rows) for table in self.tables)

    def table(self, name: str) -> GeneratedTable:
        """Return generated data by table name."""

        for table in self.tables:
            if table.name == name:
                return table
        raise KeyError(f"Unknown generated table {name}")

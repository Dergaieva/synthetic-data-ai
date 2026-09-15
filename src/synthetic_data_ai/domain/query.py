"""Safe analytical query plans and results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QueryOperation(StrEnum):
    """Allowlisted operations translated to SQLAlchemy expressions."""

    PREVIEW = "preview"
    COUNT = "count"
    AVERAGE = "average"
    SUM = "sum"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    GROUP_COUNT = "group_count"
    GROUP_AVERAGE = "group_average"


class QueryPlan(BaseModel):
    """Validated analytical intent; deliberately not raw SQL."""

    model_config = ConfigDict(frozen=True)

    table: str
    operation: QueryOperation
    metric_column: str | None = None
    group_by_column: str | None = None
    limit: int = Field(default=50, ge=1, le=100)
    explanation: str = ""

    @model_validator(mode="after")
    def validate_required_columns(self) -> QueryPlan:
        metric_operations = {
            QueryOperation.AVERAGE,
            QueryOperation.SUM,
            QueryOperation.MINIMUM,
            QueryOperation.MAXIMUM,
            QueryOperation.GROUP_AVERAGE,
        }
        group_operations = {QueryOperation.GROUP_COUNT, QueryOperation.GROUP_AVERAGE}
        if self.operation in metric_operations and not self.metric_column:
            raise ValueError(f"{self.operation} requires metric_column")
        if self.operation in group_operations and not self.group_by_column:
            raise ValueError(f"{self.operation} requires group_by_column")
        return self


class QueryResult(BaseModel):
    """Tabular result returned to the presentation layer."""

    model_config = ConfigDict(frozen=True)

    plan: QueryPlan
    rows: tuple[dict[str, object], ...]

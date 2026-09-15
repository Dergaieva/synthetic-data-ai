"""Generation plan and generated dataset models."""

from pydantic import BaseModel, ConfigDict, Field


class GenerationPlan(BaseModel):
    """Validated user/LLM intent consumed by deterministic Python code."""

    model_config = ConfigDict(frozen=True)

    seed: int = 42
    default_rows: int = Field(default=25, ge=1, le=10_000)
    table_rows: dict[str, int] = Field(default_factory=dict)
    locale: str = "en_US"
    null_probability: float = Field(default=0.05, ge=0, le=0.5)

    def rows_for(self, table_name: str) -> int:
        """Return a table override or the plan-wide default."""

        return self.table_rows.get(table_name, self.default_rows)


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

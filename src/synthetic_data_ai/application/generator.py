"""Deterministic, constraint-aware relational data generation."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from faker import Faker

from synthetic_data_ai.domain.generation import (
    ColumnRule,
    GeneratedDataset,
    GeneratedTable,
    GenerationPlan,
    RuleKind,
)
from synthetic_data_ai.domain.schema import ColumnDefinition, DataCategory, RelationalSchema


class GenerationError(ValueError):
    """Raised when a validated schema cannot be generated safely."""


class RelationalDataGenerator:
    """Generate reproducible data while preserving foreign-key integrity."""

    def generate(
        self,
        schema: RelationalSchema,
        plan: GenerationPlan,
    ) -> GeneratedDataset:
        """Generate all tables in dependency order."""

        self._validate_plan(schema, plan)
        randomizer = random.Random(plan.seed)
        faker = Faker(plan.locale)
        faker.seed_instance(plan.seed)
        generated: dict[str, list[dict[str, object]]] = {}

        for table_name in schema.generation_order():
            table = schema.table(table_name)
            foreign_keys = {key.local_column: key for key in table.foreign_keys}
            seen_unique: dict[str, set[object]] = {
                column.name: set()
                for column in table.columns
                if column.unique or column.primary_key
            }
            rows: list[dict[str, object]] = []

            for row_index in range(plan.rows_for(table_name)):
                row: dict[str, object] = {}
                for column in table.columns:
                    foreign_key = foreign_keys.get(column.name)
                    if foreign_key is not None:
                        parent_rows = generated.get(foreign_key.referenced_table, [])
                        if not parent_rows:
                            raise GenerationError(f"No parent rows for {table_name}.{column.name}")
                        value = randomizer.choice(parent_rows)[foreign_key.referenced_column]
                    else:
                        value = self._value_for_rule(
                            table_name=table_name,
                            column=column,
                            row_index=row_index,
                            plan=plan,
                            rule=plan.rule_for(table_name, column.name),
                            randomizer=randomizer,
                            faker=faker,
                        )

                    unique_values = seen_unique.get(column.name)
                    if unique_values is not None:
                        value = self._make_unique(value, row_index, unique_values)
                        unique_values.add(value)
                    row[column.name] = value
                rows.append(row)
            generated[table_name] = rows

        return GeneratedDataset(
            seed=plan.seed,
            tables=tuple(
                GeneratedTable(name=name, rows=tuple(generated[name]))
                for name in schema.generation_order()
            ),
        )

    def _validate_plan(self, schema: RelationalSchema, plan: GenerationPlan) -> None:
        known_tables = {table.name for table in schema.tables}
        unknown = sorted(set(plan.table_rows) - known_tables)
        if unknown:
            raise GenerationError(f"Row counts provided for unknown tables: {', '.join(unknown)}")
        invalid = sorted(name for name, count in plan.table_rows.items() if count < 1)
        if invalid:
            raise GenerationError(f"Row counts must be positive: {', '.join(invalid)}")

        for table_name, column_rules in plan.column_rules.items():
            if table_name not in known_tables:
                raise GenerationError(f"Column rules reference unknown table: {table_name}")
            table = schema.table(table_name)
            foreign_key_columns = {key.local_column for key in table.foreign_keys}
            for column_name in column_rules:
                try:
                    column = table.column(column_name)
                except KeyError as error:
                    raise GenerationError(str(error)) from error
                if column.primary_key or column_name in foreign_key_columns:
                    raise GenerationError(
                        f"Rules cannot override key column {table_name}.{column_name}"
                    )

    def _value_for_rule(
        self,
        *,
        table_name: str,
        column: ColumnDefinition,
        row_index: int,
        plan: GenerationPlan,
        rule: ColumnRule,
        randomizer: random.Random,
        faker: Faker,
    ) -> object:
        if rule.kind is RuleKind.CHOICE:
            return randomizer.choice(rule.choices)
        if rule.kind is RuleKind.CONSTANT:
            return rule.value
        if rule.kind is RuleKind.INTEGER_RANGE:
            return randomizer.randint(int(rule.minimum or 0), int(rule.maximum or 0))
        if rule.kind is RuleKind.DECIMAL_RANGE:
            scale = column.scale if column.scale is not None else 2
            return Decimal(
                str(round(randomizer.uniform(rule.minimum or 0, rule.maximum or 0), scale))
            )
        return self._value_for(
            table_name=table_name,
            column=column,
            row_index=row_index,
            plan=plan,
            randomizer=randomizer,
            faker=faker,
        )

    def _value_for(
        self,
        *,
        table_name: str,
        column: ColumnDefinition,
        row_index: int,
        plan: GenerationPlan,
        randomizer: random.Random,
        faker: Faker,
    ) -> object:
        if column.primary_key:
            if column.category is DataCategory.UUID:
                return str(uuid5(NAMESPACE_URL, f"{plan.seed}:{table_name}:{row_index}"))
            if column.category is DataCategory.INTEGER:
                return row_index + 1

        if column.nullable and randomizer.random() < plan.null_probability:
            return None

        name = column.name.lower()
        if column.category is DataCategory.STRING:
            return self._string_value(name, row_index, faker, column.max_length)
        if column.category is DataCategory.INTEGER:
            if "age" in name:
                return randomizer.randint(18, 70)
            if "year" in name:
                return randomizer.randint(1990, date.today().year)
            return randomizer.randint(1, 1_000)
        if column.category is DataCategory.DECIMAL:
            lower, upper = (35_000, 180_000) if "salary" in name else (10, 10_000)
            scale = column.scale if column.scale is not None else 2
            return Decimal(str(round(randomizer.uniform(lower, upper), scale)))
        if column.category is DataCategory.BOOLEAN:
            return bool(randomizer.getrandbits(1))
        if column.category is DataCategory.DATE:
            return date.today() - timedelta(days=randomizer.randint(1, 3650))
        if column.category is DataCategory.DATETIME:
            return datetime.now(UTC) - timedelta(
                days=randomizer.randint(1, 730),
                seconds=randomizer.randint(0, 86_399),
            )
        if column.category is DataCategory.UUID:
            return str(uuid5(NAMESPACE_URL, f"{plan.seed}:{table_name}:{column.name}:{row_index}"))
        if column.category is DataCategory.JSON:
            return {"source": "synthetic", "record": row_index + 1}
        raise GenerationError(f"No generator for {table_name}.{column.name}")

    def _string_value(
        self,
        name: str,
        row_index: int,
        faker: Faker,
        max_length: int | None,
    ) -> str:
        if "email" in name:
            value = f"user{row_index + 1}@example.com"
        elif name in {"first_name", "firstname"}:
            value = faker.first_name()
        elif name in {"last_name", "lastname", "surname"}:
            value = faker.last_name()
        elif name in {"full_name", "name"}:
            value = faker.name()
        elif "city" in name:
            value = faker.city()
        elif "country" in name:
            value = faker.country()
        elif "company" in name:
            value = faker.company()
        elif "phone" in name:
            value = faker.phone_number()
        elif "address" in name:
            value = faker.address().replace("\n", ", ")
        elif "department" in name:
            departments = ("Engineering", "Product", "Finance", "People", "Sales")
            value = departments[row_index % len(departments)]
        elif "status" in name:
            statuses = ("active", "pending", "inactive")
            value = statuses[row_index % len(statuses)]
        elif any(token in name for token in ("description", "notes", "bio")):
            value = faker.sentence(nb_words=8)
        else:
            value = f"{name.replace('_', ' ').title()} {row_index + 1}"
        return value[:max_length] if max_length else value

    def _make_unique(
        self,
        value: object,
        row_index: int,
        seen: set[object],
    ) -> object:
        if value not in seen:
            return value
        if isinstance(value, str):
            return f"{value}-{row_index + 1}"
        if isinstance(value, int):
            candidate = value + row_index + 1
            while candidate in seen:
                candidate += 1
            return candidate
        return str(uuid5(NAMESPACE_URL, f"unique:{value}:{row_index}"))

"""Database adapter tests."""

from synthetic_data_ai.domain.models import ComponentStatus
from synthetic_data_ai.infrastructure.database import build_engine, check_database


def test_sqlite_health_check_is_ready() -> None:
    engine = build_engine("sqlite+pysqlite:///:memory:")

    health = check_database(engine)

    assert health.status is ComponentStatus.READY
    assert health.detail == "Connected"

"""SQLAlchemy engine construction and safe health checks."""

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from synthetic_data_ai.domain.models import ComponentHealth, ComponentStatus


def build_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine without opening a connection eagerly."""

    return create_engine(database_url, pool_pre_ping=True)


def check_database(engine: Engine) -> ComponentHealth:
    """Check connectivity with a constant query, never user- or LLM-generated SQL."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return ComponentHealth(
            name="Database",
            status=ComponentStatus.UNAVAILABLE,
            detail="Connection failed",
        )

    return ComponentHealth(
        name="Database",
        status=ComponentStatus.READY,
        detail="Connected",
    )

"""Shared domain models for application status."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ComponentStatus(StrEnum):
    """Health state for an application dependency."""

    READY = "ready"
    NOT_CONFIGURED = "not_configured"
    UNAVAILABLE = "unavailable"


class ComponentHealth(BaseModel):
    """Display-safe dependency health information."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: ComponentStatus
    detail: str

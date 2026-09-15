"""Optional Langfuse tracing for AI planning calls."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol

from langfuse import Langfuse

from synthetic_data_ai.config import Settings


class Observation(Protocol):
    """Small interface used by planners to record a result."""

    def update(self, *, output: Any | None = None, **kwargs: Any) -> Any:
        """Update the current observation."""


class AITracer(Protocol):
    """Trace one model call without coupling application code to Langfuse."""

    def generation(
        self,
        *,
        name: str,
        prompt: str,
        model: str,
        metadata: dict[str, object],
    ) -> AbstractContextManager[Observation]:
        """Return a context manager for one model generation."""


class NullObservation:
    """No-op observation used when Langfuse credentials are absent."""

    def update(self, *, output: Any | None = None, **kwargs: Any) -> None:
        """Intentionally discard trace data."""


class NullTracer:
    """Keep tracing optional without adding conditionals to planners."""

    @contextmanager
    def generation(
        self,
        *,
        name: str,
        prompt: str,
        model: str,
        metadata: dict[str, object],
    ) -> Iterator[Observation]:
        """Yield a no-op observation."""

        yield NullObservation()


class LangfuseTracer:
    """Langfuse v3 adapter for Gemini generations."""

    def __init__(self, client: Langfuse) -> None:
        self._client = client

    @contextmanager
    def generation(
        self,
        *,
        name: str,
        prompt: str,
        model: str,
        metadata: dict[str, object],
    ) -> Iterator[Observation]:
        """Record prompt, model, metadata, output, timing, and errors."""

        try:
            with self._client.start_as_current_observation(
                name=name,
                as_type="generation",
                input=prompt,
                model=model,
                metadata=metadata,
            ) as observation:
                yield observation
        finally:
            self._client.flush()


def build_ai_tracer(settings: Settings) -> AITracer:
    """Create an enabled Langfuse tracer or a zero-configuration no-op tracer."""

    if not settings.langfuse_enabled:
        return NullTracer()
    return LangfuseTracer(
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            environment=settings.environment,
        )
    )

"""Optional Langfuse tracing tests."""

from synthetic_data_ai.config import Settings
from synthetic_data_ai.infrastructure.observability import NullTracer, build_ai_tracer


def test_tracing_is_noop_without_credentials() -> None:
    settings = Settings(_env_file=None)

    tracer = build_ai_tracer(settings)

    assert isinstance(tracer, NullTracer)
    with tracer.generation(
        name="test",
        prompt="prompt",
        model="model",
        metadata={},
    ) as observation:
        observation.update(output={"ok": True})

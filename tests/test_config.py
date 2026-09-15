"""Configuration tests."""

from synthetic_data_ai.config import Settings


def test_settings_have_safe_local_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url.startswith("sqlite+")
    assert settings.google_cloud_project == "gd-gcp-gridu-genai"
    assert settings.use_vertex_ai is True
    assert settings.langfuse_enabled is False


def test_langfuse_requires_both_keys() -> None:
    settings = Settings(
        _env_file=None,
        LANGFUSE_PUBLIC_KEY="public",
        LANGFUSE_SECRET_KEY="secret",
    )

    assert settings.langfuse_enabled is True

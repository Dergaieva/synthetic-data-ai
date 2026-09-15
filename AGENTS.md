# Repository Guidelines

- Use Python 3.12.
- Add full type annotations to application code.
- Use Pydantic for domain and configuration schemas.
- Keep business logic out of the Streamlit UI layer.
- Never execute raw SQL produced by an LLM.
- Never commit secrets or local credential files.
- Add or update tests for every feature.
- Prefer dependency injection at infrastructure boundaries.
- Run `ruff check .`, `ruff format --check .`, and `pytest` before finishing.


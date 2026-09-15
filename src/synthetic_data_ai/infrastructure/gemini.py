"""Google Gen AI SDK adapter using Vertex AI and structured output."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from synthetic_data_ai.application.planning import (
    PlanValidationError,
    build_planning_prompt,
    validate_plan_for_schema,
)
from synthetic_data_ai.application.querying import (
    QueryPlanValidationError,
    build_query_prompt,
    validate_query_plan,
)
from synthetic_data_ai.config import Settings
from synthetic_data_ai.domain.generation import GenerationPlan
from synthetic_data_ai.domain.query import QueryPlan
from synthetic_data_ai.domain.schema import RelationalSchema
from synthetic_data_ai.infrastructure.observability import AITracer, build_ai_tracer


class GeminiPlanningError(RuntimeError):
    """Raised when Vertex AI cannot produce a valid generation plan."""


class GeminiQueryError(RuntimeError):
    """Raised when Vertex AI cannot produce a valid analytical query plan."""


class VertexGenerationPlanner:
    """Request a constrained GenerationPlan from Gemini through Vertex AI."""

    def __init__(
        self,
        settings: Settings,
        client: Any | None = None,
        tracer: AITracer | None = None,
    ) -> None:
        self._settings = settings
        self._tracer = tracer or build_ai_tracer(settings)
        self._client = client or genai.Client(
            vertexai=settings.use_vertex_ai,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

    def create_plan(
        self,
        schema: RelationalSchema,
        user_request: str,
        *,
        default_rows: int,
        seed: int,
    ) -> GenerationPlan:
        """Generate, parse, and validate an LLM-authored plan."""

        prompt = build_planning_prompt(
            schema,
            user_request,
            default_rows=default_rows,
            seed=seed,
        )
        try:
            with self._tracer.generation(
                name="create-generation-plan",
                prompt=prompt,
                model=self._settings.gemini_model,
                metadata={"table_count": len(schema.tables), "default_rows": default_rows},
            ) as observation:
                response = self._client.models.generate_content(
                    model=self._settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=GenerationPlan,
                    ),
                )
                plan = validate_plan_for_schema(schema, self._parse_response(response))
                observation.update(output=plan.model_dump(mode="json"))
                return plan
        except (ValidationError, PlanValidationError, ValueError, TypeError) as error:
            raise GeminiPlanningError(
                f"Gemini returned an invalid generation plan: {error}"
            ) from error
        except Exception as error:
            raise GeminiPlanningError(
                "Vertex AI request failed. Check GCP authentication, project access, "
                "and model name."
            ) from error

    def _parse_response(self, response: Any) -> GenerationPlan:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, GenerationPlan):
            return parsed
        if parsed is not None:
            return GenerationPlan.model_validate(parsed)

        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Gemini response did not contain a plan")
        return GenerationPlan.model_validate_json(text)


class VertexQueryPlanner:
    """Translate a natural-language question into a guarded QueryPlan."""

    def __init__(
        self,
        settings: Settings,
        client: Any | None = None,
        tracer: AITracer | None = None,
    ) -> None:
        self._settings = settings
        self._tracer = tracer or build_ai_tracer(settings)
        self._client = client or genai.Client(
            vertexai=settings.use_vertex_ai,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

    def create_plan(self, schema: RelationalSchema, question: str) -> QueryPlan:
        """Generate and validate analytical intent without accepting SQL."""

        prompt = build_query_prompt(schema, question)
        try:
            with self._tracer.generation(
                name="create-query-plan",
                prompt=prompt,
                model=self._settings.gemini_model,
                metadata={"table_count": len(schema.tables)},
            ) as observation:
                response = self._client.models.generate_content(
                    model=self._settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema=QueryPlan,
                    ),
                )
                plan = validate_query_plan(schema, self._parse_response(response))
                observation.update(output=plan.model_dump(mode="json"))
                return plan
        except (ValidationError, QueryPlanValidationError, ValueError, TypeError) as error:
            raise GeminiQueryError(f"Gemini returned an invalid query plan: {error}") from error
        except Exception as error:
            raise GeminiQueryError(
                "Vertex AI query planning failed. Check GCP authentication and project access."
            ) from error

    def _parse_response(self, response: Any) -> QueryPlan:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, QueryPlan):
            return parsed
        if parsed is not None:
            return QueryPlan.model_validate(parsed)
        text = getattr(response, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Gemini response did not contain a query plan")
        return QueryPlan.model_validate_json(text)

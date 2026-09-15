"""Interfaces implemented by external infrastructure."""

from typing import Protocol


class TextGenerationClient(Protocol):
    """Minimal boundary for an LLM text-generation provider."""

    def generate(self, prompt: str) -> str:
        """Generate a text response for a validated application prompt."""

        ...

"""LLM provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class LLMProvider(ABC):
    """Abstract provider. Methods return structured dicts, not raw text,
    so MVP pipelines can stay provider-agnostic without a JSON parser.
    Real providers (OpenAI/Anthropic) should wrap their completion API
    and parse JSON output inside their own implementation.
    """

    name: str = "base"

    @abstractmethod
    def generate_ideas(
        self,
        role: str,
        system_prompt: str,
        problem: str,
        constraints: List[str],
        context: str,
        round_index: int,
        prior_fragments: List[Dict[str, Any]] | None = None,
        n: int = 2,
    ) -> List[Dict[str, Any]]:
        """Return list of dicts with keys: title, statement, rationale, tags."""

    @abstractmethod
    def evaluate_axis(
        self,
        judge: str,
        system_prompt: str,
        problem: str,
        idea_title: str,
        idea_statement: str,
    ) -> Dict[str, Any]:
        """Return dict with keys: score (0-5), rationale, suggestion."""

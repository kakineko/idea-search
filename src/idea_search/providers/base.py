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

    def generate_baseline(
        self,
        problem: str,
        constraints: List[str],
        context: str,
        n: int = 3,
    ) -> List[Dict[str, Any]]:
        """Single-shot naive generation. Default falls back to the generic
        'Proposer' role so providers that don't specialize still work.
        Returns list of dicts with title, statement, rationale, tags.
        """
        return self.generate_ideas(
            role="Proposer",
            system_prompt="",
            problem=problem,
            constraints=constraints,
            context=context,
            round_index=0,
            prior_fragments=None,
            n=n,
        )

    def self_critique(
        self,
        problem: str,
        ideas: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Take a list of idea dicts, produce a revised list via the same
        model critiquing its own output. Default is a no-op passthrough.
        """
        return ideas

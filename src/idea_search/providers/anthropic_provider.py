"""Anthropic provider stub. Not implemented in v1."""
from __future__ import annotations

from typing import List, Dict, Any

from idea_search.providers.base import LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def generate_ideas(self, *args, **kwargs) -> List[Dict[str, Any]]:
        raise NotImplementedError(
            "AnthropicProvider is a stub in v1. Use provider='mock' for now."
        )

    def evaluate_axis(self, *args, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError(
            "AnthropicProvider is a stub in v1. Use provider='mock' for now."
        )

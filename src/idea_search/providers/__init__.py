from idea_search.providers.base import LLMProvider
from idea_search.providers.mock import MockProvider


def get_provider(name: str) -> LLMProvider:
    name = name.lower()
    if name == "mock":
        return MockProvider()
    if name == "openai":
        from idea_search.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    if name == "anthropic":
        from idea_search.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider()
    if name == "claude-cli":
        from idea_search.providers.claude_cli_provider import ClaudeCLIProvider
        return ClaudeCLIProvider()
    raise ValueError(f"Unknown provider: {name}")

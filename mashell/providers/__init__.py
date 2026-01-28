"""Providers package - LLM provider implementations."""

from mashell.providers.anthropic import AnthropicProvider
from mashell.providers.azure import AzureProvider
from mashell.providers.base import BaseProvider, Message, Response, ToolCall
from mashell.providers.ollama import OllamaProvider
from mashell.providers.openai import OpenAIProvider

__all__ = [
    "BaseProvider",
    "Message",
    "ToolCall",
    "Response",
    "OpenAIProvider",
    "AzureProvider",
    "AnthropicProvider",
    "OllamaProvider",
]


def create_provider(provider_type: str, url: str, key: str | None, model: str) -> BaseProvider:
    """Factory function to create a provider instance."""
    providers = {
        "openai": OpenAIProvider,
        "azure": AzureProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }

    if provider_type not in providers:
        raise ValueError(f"Unknown provider: {provider_type}. Supported: {list(providers.keys())}")

    return providers[provider_type](url, key, model)

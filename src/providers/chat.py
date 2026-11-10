from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from src.providers.errors import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from src.providers.protocols import ChatMessage


def translate_provider_error(exc: Exception, provider: str) -> ProviderError:
    """Translate SDK errors without exposing request bodies, prompts, or secrets."""
    if isinstance(exc, AuthenticationError):
        return ProviderAuthenticationError(provider)
    if isinstance(exc, APITimeoutError):
        return ProviderTimeoutError(provider)
    if isinstance(exc, RateLimitError):
        return ProviderRateLimitError(provider)
    if isinstance(exc, (APIConnectionError, APIStatusError)):
        return ProviderUnavailableError(provider)
    if isinstance(exc, ProviderError):
        return exc
    return ProviderUnavailableError(provider)


class OpenAICompatibleChatProvider:
    """Common adapter for OpenAI and OpenAI-compatible chat APIs."""

    def __init__(
        self,
        *,
        client: OpenAI,
        model: str,
        provider_name: str,
    ) -> None:
        self._client = client
        self.model = model
        self.provider_name = provider_name

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        try:
            request: dict[str, Any] = {
                "model": self.model,
                "messages": list(messages),
                "temperature": temperature,
            }
            if max_tokens is not None:
                request["max_tokens"] = max_tokens
            if response_format is not None:
                request["response_format"] = response_format
            response = self._client.chat.completions.create(
                **request,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            raise translate_provider_error(exc, self.provider_name) from exc

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]:
        try:
            request: dict[str, Any] = {
                "model": self.model,
                "messages": list(messages),
                "temperature": temperature,
                "stream": True,
            }
            if max_tokens is not None:
                request["max_tokens"] = max_tokens
            if response_format is not None:
                request["response_format"] = response_format
            response = self._client.chat.completions.create(**request)
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as exc:
            raise translate_provider_error(exc, self.provider_name) from exc


class OpenAIChatProvider(OpenAICompatibleChatProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float,
        max_retries: int,
        base_url: str | None = None,
    ) -> None:
        client_options: dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            client_options["base_url"] = base_url
        super().__init__(
            client=OpenAI(**client_options),
            model=model,
            provider_name="openai",
        )


class OllamaChatProvider(OpenAICompatibleChatProvider):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        super().__init__(
            client=OpenAI(
                base_url=base_url,
                api_key="ollama",
                timeout=timeout,
                max_retries=max_retries,
            ),
            model=model,
            provider_name="ollama",
        )

from __future__ import annotations

from collections.abc import Iterator, Sequence

from src.providers.protocols import ChatMessage


class FakeChatProvider:
    """Deterministic provider for chatbot unit tests."""

    provider_name = "fake"
    model = "fake-model"

    def __init__(
        self,
        completions: list[str] | None = None,
        stream_tokens: list[str] | None = None,
    ) -> None:
        self.completions = list(completions or [])
        self.stream_tokens = list(stream_tokens or [])
        self.complete_calls: list[dict] = []
        self.stream_calls: list[dict] = []

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str:
        self.complete_calls.append(
            {
                "messages": list(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        if not self.completions:
            raise AssertionError("No fake completion configured")
        return self.completions.pop(0)

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]:
        self.stream_calls.append(
            {
                "messages": list(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": response_format,
            }
        )
        yield from self.stream_tokens

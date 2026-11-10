from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Protocol, TypedDict, runtime_checkable

import numpy as np


class ChatMessage(TypedDict):
    role: str
    content: str


@runtime_checkable
class ChatCompletionProvider(Protocol):
    provider_name: str
    model: str

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> str: ...


@runtime_checkable
class StreamingCompletionProvider(Protocol):
    provider_name: str
    model: str

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> Iterator[str]: ...


class ChatProvider(ChatCompletionProvider, StreamingCompletionProvider, Protocol):
    pass


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def name(self) -> str: ...

    def embed_query(self, query: str) -> np.ndarray: ...

    def embed_batch(self, texts: list[str]) -> np.ndarray: ...


@runtime_checkable
class QueryExpansionProvider(Protocol):
    def expand(self, query: str) -> list[str]: ...

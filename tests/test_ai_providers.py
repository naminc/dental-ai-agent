from types import SimpleNamespace

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from src.providers.chat import OpenAICompatibleChatProvider
from src.providers.errors import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from src.providers.factory import get_chat_provider


class RaisingCompletions:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def create(self, **kwargs):
        raise self.error


def fake_client(error: Exception):
    return SimpleNamespace(
        chat=SimpleNamespace(completions=RaisingCompletions(error))
    )


def response(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://provider.invalid/v1/chat/completions")
    return httpx.Response(status_code, request=request)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("sdk_error", "application_error"),
    [
        (
            AuthenticationError("bad credentials", response=response(401), body=None),
            ProviderAuthenticationError,
        ),
        (
            APITimeoutError(request=httpx.Request("POST", "https://provider.invalid")),
            ProviderTimeoutError,
        ),
        (
            RateLimitError("limited", response=response(429), body=None),
            ProviderRateLimitError,
        ),
        (
            APIConnectionError(
                request=httpx.Request("POST", "https://provider.invalid")
            ),
            ProviderUnavailableError,
        ),
    ],
)
def test_sdk_errors_are_translated_to_safe_application_errors(
    sdk_error: Exception,
    application_error: type[Exception],
) -> None:
    provider = OpenAICompatibleChatProvider(
        client=fake_client(sdk_error),
        model="fake-model",
        provider_name="test-provider",
    )

    with pytest.raises(application_error) as error:
        provider.complete(
            [{"role": "user", "content": "sensitive prompt"}],
            temperature=0,
        )

    assert "sensitive prompt" not in str(error.value)
    assert "bad credentials" not in str(error.value)


@pytest.mark.unit
def test_provider_factory_reuses_one_provider_per_process(monkeypatch) -> None:
    created = []

    class StubProvider:
        def __init__(self, **kwargs):
            created.append(kwargs)

    get_chat_provider.cache_clear()
    monkeypatch.setattr("src.providers.factory.OllamaChatProvider", StubProvider)
    try:
        first = get_chat_provider("local", "test-model")
        second = get_chat_provider("local", "test-model")
    finally:
        get_chat_provider.cache_clear()

    assert first is second
    assert len(created) == 1

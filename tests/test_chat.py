import json

import pytest

from api.main import app
from src.chat.dependencies import get_chatbot
from src.database.models import Message
from src.providers.errors import ProviderTimeoutError


class FakeChatbot:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def answer_stream(self, user_question: str, chat_history: list[dict]):
        self.calls.append(
            {
                "user_question": user_question,
                "chat_history": chat_history,
            }
        )
        yield "Câu trả "
        yield "lời giả lập."
        yield {
            "sources": [{"title": "Test source"}],
            "rewritten_query": "câu hỏi đã viết lại",
        }


def parse_sse(response_text: str) -> list[dict]:
    events = []
    for block in response_text.strip().split("\n\n"):
        assert block.startswith("data: "), f"Invalid SSE block: {block!r}"
        events.append(json.loads(block.removeprefix("data: ")))
    return events


@pytest.mark.integration
def test_chat_streams_fake_llm_and_persists_messages(
    client,
    auth_headers,
    db_session_factory,
) -> None:
    fake_chatbot = FakeChatbot()
    app.dependency_overrides[get_chatbot] = lambda: fake_chatbot

    response = client.post(
        "/api/chat",
        headers=auth_headers,
        json={
            "session_id": "session-test-1",
            "user_question": "Tôi nên chăm sóc răng thế nào?",
            "chat_history": [{"role": "user", "content": "Xin chào"}],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["x-accel-buffering"] == "no"

    events = parse_sse(response.text)
    assert [event["token"] for event in events[:-1]] == [
        "Câu trả ",
        "lời giả lập.",
    ]
    assert events[-1] == {
        "done": True,
        "sources": [{"title": "Test source"}],
        "rewritten_query": "câu hỏi đã viết lại",
    }
    assert fake_chatbot.calls == [
        {
            "user_question": "Tôi nên chăm sóc răng thế nào?",
            "chat_history": [{"role": "user", "content": "Xin chào"}],
        }
    ]

    session = db_session_factory()
    try:
        messages = session.query(Message).order_by(Message.id.asc()).all()
        assert [(message.role, message.content) for message in messages] == [
            ("user", "Tôi nên chăm sóc răng thế nào?"),
            ("assistant", "Câu trả lời giả lập."),
        ]
        assert json.loads(messages[1].sources) == [{"title": "Test source"}]
        assert messages[1].rewritten_query == "câu hỏi đã viết lại"
    finally:
        session.close()


@pytest.mark.integration
def test_chat_stream_returns_safe_provider_error_without_changing_sse_shape(
    client,
    auth_headers,
) -> None:
    class FailingChatbot:
        def answer_stream(self, user_question: str, chat_history: list[dict]):
            raise ProviderTimeoutError("openai")
            yield  # pragma: no cover - keeps this method a generator

    app.dependency_overrides[get_chatbot] = lambda: FailingChatbot()
    response = client.post(
        "/api/chat",
        headers=auth_headers,
        json={
            "session_id": "provider-timeout-session",
            "user_question": "sensitive question must not appear in logs",
            "chat_history": [],
        },
    )

    assert response.status_code == 200
    assert parse_sse(response.text) == [
        {"error": ProviderTimeoutError.public_message}
    ]

import pytest

from src.agent.chatbot import DentalChatbot
from src.providers.fake import FakeChatProvider


class FakeRetriever:
    def __init__(self) -> None:
        self.search_calls = []

    def get_available_diseases(self):
        return ["sâu răng", "viêm nướu"]

    def expand_queries(self, query):
        return [query, "biến thể"]

    def search(self, query, categories=None, expanded_queries=None):
        self.search_calls.append((query, categories, expanded_queries))
        return [
            {
                "title": "Sâu răng là gì",
                "section": "Tổng quan",
                "summary": "Thông tin tóm tắt",
                "content": "Nội dung kiểm thử",
                "source": "test-source",
            }
        ]


@pytest.mark.unit
def test_chatbot_pipeline_uses_fake_provider_and_preserves_stream_contract() -> None:
    provider = FakeChatProvider(
        completions=["câu hỏi đã viết lại", "sâu răng"],
        stream_tokens=["Câu trả ", "lời giả lập."],
    )
    retriever = FakeRetriever()
    chatbot = DentalChatbot(
        llm_engine="openai",
        chat_provider=provider,
        retriever=retriever,
    )

    output = list(chatbot.answer_stream("Tôi bị đau răng", []))

    assert output[:2] == ["Câu trả ", "lời giả lập."]
    assert output[-2].startswith("\n\n*")
    assert output[-1] == {
        "sources": [
            {
                "title": "Sâu răng là gì",
                "section": "Tổng quan",
                "summary": "Thông tin tóm tắt",
                "content": "Nội dung kiểm thử",
                "source": "test-source",
            }
        ],
        "rewritten_query": "câu hỏi đã viết lại",
    }
    assert retriever.search_calls == [
        (
            "câu hỏi đã viết lại",
            ["sâu răng"],
            ["câu hỏi đã viết lại", "biến thể"],
        )
    ]
    assert len(provider.complete_calls) == 2
    assert len(provider.stream_calls) == 1

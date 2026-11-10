import logging
import threading
import time
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

if TYPE_CHECKING:
    from src.agent.chatbot import DentalChatbot

logger = logging.getLogger(__name__)

_chatbot: "DentalChatbot | None" = None
_chatbot_lock = threading.Lock()
_last_initialization = "not_attempted"


def get_chatbot() -> "DentalChatbot":
    """Lazily initialize one chatbot per worker and convert failures to HTTP 503."""
    global _chatbot, _last_initialization

    if _chatbot is not None:
        return _chatbot

    with _chatbot_lock:
        if _chatbot is not None:
            return _chatbot

        started_at = time.perf_counter()
        _last_initialization = "in_progress"
        try:
            # Keep FAISS/NLP/model imports off the application import path.
            from src.agent.chatbot import DentalChatbot
            from src.core.settings import get_settings
            from src.providers.factory import get_chat_provider

            settings = get_settings()
            _chatbot = DentalChatbot(
                chat_provider=get_chat_provider(settings.llm_engine.value),
                llm_engine=settings.llm_engine.value,
                embedding_engine=settings.embedding_engine.value,
            )
            _last_initialization = "succeeded"
            logger.info(
                "[CHATBOT] Initialized lazily in %.2fs",
                time.perf_counter() - started_at,
            )
        except Exception as exc:
            _last_initialization = "failed"
            logger.exception("[CHATBOT] Lazy initialization failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Dịch vụ trợ lý AI tạm thời chưa sẵn sàng. Vui lòng thử lại sau.",
            ) from exc

    return _chatbot


def get_chatbot_status() -> dict[str, bool | str]:
    """Return process-local state without triggering chatbot initialization."""
    return {
        "initialized": _chatbot is not None,
        "last_initialization": _last_initialization,
    }

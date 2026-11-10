import sys
from pathlib import Path

from fastapi import FastAPI, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.auth import router as auth_router
from src.chat import router as chat_router
from src.chat.dependencies import get_chatbot_status
from src.core.settings import Engine, get_settings
from src.database.database import engine
from api.lifespan import lifespan
from api.exception_handlers import register_exception_handlers
from api.security import SecurityHeadersMiddleware

settings = get_settings()

# Khởi tạo app
app = FastAPI(title="Dental AI API", version="1.0.0", lifespan=lifespan)

# Đăng ký xử lý lỗi
register_exception_handlers(app)

app.add_middleware(SecurityHeadersMiddleware)

# CORS: credentialed requests must use explicit, trusted frontend origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Health check
app.get("/")(lambda: {"message": "FastAPI is running"})


# Health check
@app.get("/health")
def health():
    return {"status": "ok"}


def _check_database() -> bool:
    """Run the database probe outside the event loop."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_retriever() -> dict[str, object]:
    """Load and validate the selected index only when readiness is requested."""
    try:
        from src.retriever.index_store import IndexStore

        index_dir = settings.vector_db_dir / settings.embedding_engine.value
        store = IndexStore(index_dir, settings.embedding_engine.value)
        if store.index.ntotal != len(store.metadata):
            return {
                "ready": False,
                "index": "available",
                "metadata": "available",
                "integrity": "mismatch",
            }
        return {
            "ready": True,
            "index": "available",
            "metadata": "available",
            "integrity": "valid",
        }
    except FileNotFoundError as exc:
        missing = "index" if "index not found" in str(exc) else "metadata"
        return {
            "ready": False,
            "index": "missing" if missing == "index" else "unknown",
            "metadata": "missing" if missing == "metadata" else "unknown",
            "integrity": "not_checked",
        }
    except Exception:
        return {
            "ready": False,
            "index": "unreadable",
            "metadata": "unreadable",
            "integrity": "invalid",
        }


@app.get("/ready")
async def ready(response: Response):
    """Report readiness without initializing the chatbot or calling an LLM."""
    database_ready = await run_in_threadpool(_check_database)
    retriever_check = await run_in_threadpool(_check_retriever)
    chatbot_status = get_chatbot_status()
    embedding_config_ready = (
        settings.embedding_engine is not Engine.OPENAI
        or bool(settings.openai_api_key_value)
    )
    chatbot_config_ready = (
        settings.llm_engine is not Engine.OPENAI
        or bool(settings.openai_api_key_value)
    )
    retriever_ready = bool(retriever_check["ready"]) and embedding_config_ready
    chatbot_ready = (
        chatbot_config_ready
        and chatbot_status["last_initialization"] != "failed"
    )

    is_ready = database_ready and retriever_ready and chatbot_ready
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": {
            "database": {
                "status": "ready" if database_ready else "unavailable",
            },
            "retriever": {
                "status": "ready" if retriever_ready else "unavailable",
                "engine": settings.embedding_engine.value,
                "index": retriever_check["index"],
                "metadata": retriever_check["metadata"],
                "integrity": retriever_check["integrity"],
                "configuration": "valid" if embedding_config_ready else "invalid",
            },
            "chatbot": {
                "status": "ready" if chatbot_ready else "unavailable",
                "initialized": chatbot_status["initialized"],
                "last_initialization": chatbot_status["last_initialization"],
            },
        },
    }


# Routers
app.include_router(auth_router.router)
app.include_router(chat_router.router)

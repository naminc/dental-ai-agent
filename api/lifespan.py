import logging
import logging.handlers
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.core.settings import get_settings
from src.database.database import engine

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure logging
_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Configure logging
def _configure_logging() -> None:
    level_name = settings.log_level
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    target_log_path = str(settings.log_file)
    has_file = any(
        isinstance(h, logging.handlers.TimedRotatingFileHandler)
        and str(getattr(h, "baseFilename", "")) == target_log_path
        for h in root.handlers
    )

    if not has_file:
        try:
            log_path = settings.log_file
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=log_path,
                when="midnight",
                interval=1,
                backupCount=30,
                encoding="utf-8",
            )
            file_handler.setFormatter(_FORMATTER)
            root.addHandler(file_handler)
        except Exception as e:
            sys.stderr.write(f"[LOG] Không thể mở file log '{settings.log_file}': {e}\n")

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger.info("[STARTUP] Web process ready; external dependencies are lazy-loaded.")

    yield

    try:
        engine.dispose()
        logger.info("[SHUTDOWN] Đã giải phóng connection pool")
    except Exception as e:
        logger.warning("[SHUTDOWN] Lỗi khi dispose engine: %s", e)

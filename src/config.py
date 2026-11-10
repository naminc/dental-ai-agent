"""Backward-compatible exports for scripts that still import ``src.config``.

New application code should use ``get_settings()`` from ``src.core.settings``.
"""

from src.core.settings import BASE_DIR, get_settings


_settings = get_settings()

RAW_DATA_PATH = _settings.raw_data_path
RAW_DATA_V2_PATH = _settings.raw_data_v2_path
PROCESSED_DATA_PATH = _settings.processed_data_path
VECTOR_DB_DIR = _settings.vector_db_dir

EMBEDDING_ENGINE = _settings.embedding_engine.value
LLM_ENGINE = _settings.llm_engine.value

OPENAI_API_KEY = _settings.openai_api_key_value
OPENAI_CHAT_MODEL = _settings.openai_chat_model
OPENAI_EMBEDDING_MODEL = _settings.openai_embedding_model
OPENAI_EMBEDDING_DIM = _settings.openai_embedding_dim

OLLAMA_BASE_URL = _settings.ollama_base_url
OLLAMA_CHAT_MODEL = _settings.ollama_chat_model

LOCAL_EMBEDDING_MODEL = _settings.local_embedding_model
LOCAL_EMBEDDING_DIM = _settings.local_embedding_dim

DATABASE_URL = _settings.database_url
SECRET_KEY = _settings.secret_key_value
ALGORITHM = _settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = _settings.access_token_expire_minutes

MULTI_QUERY_EXPANSION = _settings.multi_query_expansion
TOP_K = _settings.top_k

UPGRADE_DATASET_MODEL = _settings.upgrade_dataset_model
AUTO_PIPELINE_MODEL = _settings.auto_pipeline_model

LOG_FILE = _settings.log_file

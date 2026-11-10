import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from src.core.settings import Engine, Settings, get_settings


BASE_VALUES = {
    "database_url": "mysql+pymysql://user:password@127.0.0.1:3306/test_db",
    "secret_key": "test-secret-key",
}


class SettingsTests(unittest.TestCase):
    def test_production_requires_strong_secret_and_explicit_cors(self):
        with self.assertRaisesRegex(ValidationError, "at least 32 characters"):
            Settings(
                _env_file=None,
                **BASE_VALUES,
                app_env="production",
                embedding_engine="local",
                llm_engine="local",
                cors_origins=["https://app.example.com"],
            )

        with self.assertRaisesRegex(ValidationError, "CORS_ORIGINS is required"):
            Settings(
                _env_file=None,
                database_url=BASE_VALUES["database_url"],
                secret_key="x" * 32,
                app_env="production",
                embedding_engine="local",
                llm_engine="local",
            )

    def test_cors_rejects_wildcard_and_path(self):
        for origin in ("*", "https://app.example.com/api"):
            with self.assertRaises(ValidationError):
                Settings(
                    _env_file=None,
                    **BASE_VALUES,
                    embedding_engine="local",
                    llm_engine="local",
                    cors_origins=[origin],
                )

    def test_openai_mode_requires_and_accepts_api_key(self):
        settings = Settings(
            _env_file=None,
            **BASE_VALUES,
            embedding_engine="openai",
            llm_engine="openai",
            openai_api_key="test-openai-key",
        )

        self.assertEqual(settings.embedding_engine, Engine.OPENAI)
        self.assertEqual(settings.llm_engine, Engine.OPENAI)
        self.assertEqual(settings.openai_api_key_value, "test-openai-key")
        self.assertNotIn("test-openai-key", repr(settings))

    def test_local_mode_does_not_require_openai_api_key(self):
        settings = Settings(
            _env_file=None,
            **BASE_VALUES,
            embedding_engine="local",
            llm_engine="local",
            openai_api_key=None,
        )

        self.assertEqual(settings.embedding_engine, Engine.LOCAL)
        self.assertEqual(settings.llm_engine, Engine.LOCAL)
        self.assertIsNone(settings.openai_api_key_value)

    def test_missing_openai_api_key_has_clear_error(self):
        with self.assertRaisesRegex(
            ValidationError,
            "OPENAI_API_KEY is required",
        ):
            Settings(
                _env_file=None,
                **BASE_VALUES,
                embedding_engine="local",
                llm_engine="openai",
                openai_api_key=None,
            )

    def test_missing_required_database_and_secret_has_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValidationError) as context:
                Settings(
                    _env_file=None,
                    embedding_engine="local",
                    llm_engine="local",
                )

        errors = context.exception.errors()
        missing_fields = {error["loc"][0] for error in errors}
        self.assertEqual(missing_fields, {"database_url", "secret_key"})

    def test_environment_has_priority_over_dotenv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "DATABASE_URL=mysql+pymysql://file:file@localhost/file_db\n"
                "SECRET_KEY=file-secret\n"
                "EMBEDDING_ENGINE=local\n"
                "LLM_ENGINE=local\n"
                "TOP_K=3\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"TOP_K": "17"}, clear=False):
                settings = Settings(_env_file=env_file)

        self.assertEqual(settings.top_k, 17)

    def test_loading_settings_does_not_use_network(self):
        with patch.object(
            socket.socket,
            "connect",
            side_effect=AssertionError("settings attempted a network connection"),
        ):
            settings = Settings(
                _env_file=None,
                **BASE_VALUES,
                embedding_engine="local",
                llm_engine="local",
            )

        self.assertEqual(settings.database_url, BASE_VALUES["database_url"])

    def test_provider_transport_settings_are_validated(self):
        settings = Settings(
            _env_file=None,
            **BASE_VALUES,
            embedding_engine="local",
            llm_engine="local",
            provider_timeout_seconds=12.5,
            provider_max_retries=4,
        )

        self.assertEqual(settings.provider_timeout_seconds, 12.5)
        self.assertEqual(settings.provider_max_retries, 4)
        self.assertIsNone(settings.openai_base_url)

        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                **BASE_VALUES,
                embedding_engine="local",
                llm_engine="local",
                provider_timeout_seconds=0,
            )

    def test_get_settings_is_cached(self):
        environment = {
            "DATABASE_URL": BASE_VALUES["database_url"],
            "SECRET_KEY": BASE_VALUES["secret_key"],
            "EMBEDDING_ENGINE": "local",
            "LLM_ENGINE": "local",
        }
        get_settings.cache_clear()
        try:
            with patch.dict(os.environ, environment, clear=True):
                first = get_settings()
                second = get_settings()
            self.assertIs(first, second)
        finally:
            get_settings.cache_clear()


if __name__ == "__main__":
    unittest.main()

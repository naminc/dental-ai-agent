import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def migration_environment(database_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "SECRET_KEY": "test-only-migration-secret",
            "EMBEDDING_ENGINE": "local",
            "LLM_ENGINE": "local",
            "OPENAI_API_KEY": " ",
        }
    )
    return environment


class MigrationTests(unittest.TestCase):
    def run_alembic(self, *arguments: str, environment: dict[str, str]) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=PROJECT_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_upgrade_is_idempotent_and_downgrade_removes_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "migration_test.db"
            environment = migration_environment(database_path)
            database_url = environment["DATABASE_URL"]

            self.run_alembic("upgrade", "head", environment=environment)
            database_engine = create_engine(database_url)
            try:
                schema = inspect(database_engine)
                self.assertEqual(
                    set(schema.get_table_names()),
                    {"alembic_version", "users", "chat_sessions", "messages"},
                )
                self.assertTrue(
                    any(
                        index["name"] == "ix_users_email" and index["unique"]
                        for index in schema.get_indexes("users")
                    )
                )
                self.assertEqual(
                    schema.get_foreign_keys("chat_sessions")[0]["referred_table"],
                    "users",
                )
                self.assertEqual(
                    schema.get_foreign_keys("messages")[0]["referred_table"],
                    "chat_sessions",
                )
            finally:
                database_engine.dispose()

            self.run_alembic("upgrade", "head", environment=environment)
            self.run_alembic("check", environment=environment)
            self.run_alembic("downgrade", "-1", environment=environment)

            database_engine = create_engine(database_url)
            try:
                schema = inspect(database_engine)
                self.assertFalse(
                    {"users", "chat_sessions", "messages"}
                    & set(schema.get_table_names())
                )
            finally:
                database_engine.dispose()

    def test_importing_fastapi_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "import_test.db"
            environment = migration_environment(database_path)

            subprocess.run(
                [sys.executable, "-c", "import api.main"],
                cwd=PROJECT_ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertFalse(database_path.exists())


if __name__ == "__main__":
    unittest.main()

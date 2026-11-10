import os
import subprocess
import sys
from pathlib import Path

import pytest

from api import main as api_main
from src.core.settings import Settings


@pytest.mark.unit
def test_import_does_not_access_network_or_create_database(tmp_path: Path) -> None:
    database_path = tmp_path / "import_must_not_create.db"
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": f"sqlite:///{database_path.as_posix()}",
            "SECRET_KEY": "subprocess-test-secret",
            "EMBEDDING_ENGINE": "local",
            "LLM_ENGINE": "local",
            "OPENAI_API_KEY": " ",
        }
    )
    script = (
        "import socket; "
        "socket.socket.connect = lambda *a, **k: "
        "(_ for _ in ()).throw(AssertionError('network attempted during import')); "
        "import api.main; print('IMPORT_OK')"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "IMPORT_OK"
    assert not database_path.exists(), "Importing api.main created a database file"


@pytest.mark.integration
def test_health_reports_process_liveness(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.integration
def test_cors_allows_only_configured_origin(client) -> None:
    original = list(api_main.settings.cors_origins)
    api_main.settings.cors_origins[:] = ["https://app.example.com"]
    try:
        allowed = client.options(
            "/health",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        denied = client.options(
            "/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    finally:
        api_main.settings.cors_origins[:] = original

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.integration
def test_ready_reports_ready_without_initializing_chatbot(
    client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_dir = tmp_path / "vector_db" / "local"
    index_dir.mkdir(parents=True)
    (index_dir / "faiss.index").write_bytes(b"test-index-placeholder")
    (index_dir / "metadata.json").write_text("[]", encoding="utf-8")
    test_settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        secret_key="ready-test-secret",
        embedding_engine="local",
        llm_engine="local",
        vector_db_dir=tmp_path / "vector_db",
    )
    monkeypatch.setattr(api_main, "settings", test_settings)
    monkeypatch.setattr(api_main, "_check_database", lambda: True)
    monkeypatch.setattr(
        api_main,
        "_check_retriever",
        lambda: {
            "ready": True,
            "index": "available",
            "metadata": "available",
            "integrity": "valid",
        },
    )
    monkeypatch.setattr(
        api_main,
        "get_chatbot_status",
        lambda: {"initialized": False, "last_initialization": "not_attempted"},
    )

    response = client.get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["database"]["status"] == "ready"
    assert payload["checks"]["retriever"]["status"] == "ready"
    assert payload["checks"]["chatbot"]["initialized"] is False


@pytest.mark.integration
def test_ready_returns_503_when_database_is_unavailable(
    client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        secret_key="ready-test-secret",
        embedding_engine="local",
        llm_engine="local",
        vector_db_dir=tmp_path / "missing-vector-db",
    )
    monkeypatch.setattr(api_main, "settings", test_settings)
    monkeypatch.setattr(api_main, "_check_database", lambda: False)
    monkeypatch.setattr(
        api_main,
        "_check_retriever",
        lambda: {
            "ready": False,
            "index": "missing",
            "metadata": "unknown",
            "integrity": "not_checked",
        },
    )

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["database"]["status"] == "unavailable"

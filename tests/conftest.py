import os
import socket
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


# Set deterministic test configuration before importing application modules.
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "mysql+pymysql://test:test@127.0.0.1:1/test_only",
        "SECRET_KEY": "pytest-only-secret-key",
        "EMBEDDING_ENGINE": "local",
        "LLM_ENGINE": "local",
        "OPENAI_API_KEY": " ",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
)

from api.main import app  # noqa: E402
from src.chat import router as chat_router  # noqa: E402
from src.database.database import Base, get_db  # noqa: E402
from src.database.models import User  # noqa: E402


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    original_connect = socket.socket.connect

    def guarded_connect(sock, address):
        # Windows creates an internal loopback socketpair for each asyncio event
        # loop. Allow only that ephemeral control channel; block service ports
        # such as MySQL, Ollama, OpenAI proxies, and every remote host.
        if (
            isinstance(address, tuple)
            and address[0] in {"127.0.0.1", "::1"}
            and address[1] >= 49152
        ):
            return original_connect(sock, address)
        raise AssertionError("External network access is forbidden in backend tests")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture
def db_session_factory(
    tmp_path: Path,
) -> Iterator[sessionmaker[Session]]:
    database_path = tmp_path / "backend_test.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    try:
        yield TestingSessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(db_session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(
    db_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(chat_router, "SessionLocal", db_session_factory)

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.clear()


@pytest.fixture
def create_user(
    db_session_factory: sessionmaker[Session],
) -> Callable[..., User]:
    from src.auth.utils import get_password_hash

    def factory(
        *,
        email: str = "user@example.com",
        password: str = "test-password",
        full_name: str = "Test User",
    ) -> User:
        session = db_session_factory()
        try:
            user = User(
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(password),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            session.expunge(user)
            return user
        finally:
            session.close()

    return factory


@pytest.fixture
def auth_headers(create_user: Callable[..., User]) -> dict[str, str]:
    from src.auth.utils import create_access_token

    user = create_user()
    token = create_access_token({"sub": user.email, "user_id": user.id})
    return {"Authorization": f"Bearer {token}"}

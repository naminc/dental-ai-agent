from datetime import timedelta

import pytest

from src.auth.utils import create_access_token


REGISTER_PAYLOAD = {
    "full_name": "Dental Test User",
    "email": "dental@example.com",
    "password": "strong-password",
    "confirm_password": "strong-password",
}


@pytest.mark.integration
def test_register_and_login(client) -> None:
    register_response = client.post("/api/auth/register", json=REGISTER_PAYLOAD)

    assert register_response.status_code == 201
    assert register_response.json()["email"] == REGISTER_PAYLOAD["email"]
    assert "hashed_password" not in register_response.json()

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": REGISTER_PAYLOAD["email"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )

    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["email"] == REGISTER_PAYLOAD["email"]


@pytest.mark.integration
def test_login_rejects_wrong_password(client, create_user) -> None:
    user = create_user(email="wrong-password@example.com")

    response = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "incorrect"},
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_valid_jwt_allows_current_user(client, auth_headers) -> None:
    response = client.get("/api/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


@pytest.mark.integration
@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-valid-token",
        None,
    ],
)
def test_invalid_or_missing_jwt_is_rejected(client, authorization) -> None:
    headers = {"Authorization": authorization} if authorization else {}

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code in {401, 403}


@pytest.mark.integration
def test_expired_jwt_is_rejected(client, create_user) -> None:
    user = create_user(email="expired@example.com")
    expired_token = create_access_token(
        {"sub": user.email, "user_id": user.id},
        expires_delta=timedelta(seconds=-1),
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_2fa_challenge_token_cannot_access_protected_route(client, create_user) -> None:
    user = create_user(email="two-factor@example.com")
    token = create_access_token(
        {"sub": user.email, "user_id": user.id, "purpose": "2fa_verify"},
        expires_delta=timedelta(minutes=5),
    )

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401

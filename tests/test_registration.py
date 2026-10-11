import pytest

from mod1_auth.database import create_session_factory
from mod1_auth.repositories import UserRepository

VALID = {
    "display_name": "Pessoa nova",
    "email": "nova@example.com",
    "password": "  senha-nova-12345  ",
}


def test_public_registration_can_login_immediately(client, engine):
    registered = client.post("/auth/register", json=VALID)
    assert registered.status_code == 202
    assert registered.headers["cache-control"] == "no-store"
    assert set(registered.json()) == {"message"}
    login = client.post(
        "/auth/token", data={"username": VALID["email"], "password": VALID["password"]}
    )
    assert login.status_code == 200
    identity = client.get(
        "/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}
    ).json()
    assert identity["email"] == "nova@example.com"
    assert identity["display_name"] == "Pessoa nova"
    assert identity["is_active"] is True
    with create_session_factory(engine)() as session:
        user = UserRepository(session).get_by_email("nova@example.com")
        assert user is not None and user.password_hash != VALID["password"]


def test_registration_duplicate_does_not_disclose_or_overwrite_account(client):
    first = client.post("/auth/register", json=VALID)
    duplicate = client.post(
        "/auth/register",
        json=VALID | {"email": " NOVA@EXAMPLE.COM ", "password": "outra-senha-12345"},
    )
    assert first.status_code == duplicate.status_code == 202
    assert first.json() == duplicate.json()
    assert (
        client.post(
            "/auth/token", data={"username": VALID["email"], "password": VALID["password"]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/token", data={"username": VALID["email"], "password": "outra-senha-12345"}
        ).status_code
        == 401
    )


def test_registration_does_not_reactivate_existing_account(client, user, engine):
    with create_session_factory(engine)() as session:
        UserRepository(session).set_active(user.id, False)
    response = client.post("/auth/register", json=VALID | {"email": user.email})
    assert response.status_code == 202
    with create_session_factory(engine)() as session:
        unchanged = UserRepository(session).get_by_id(user.id)
        assert unchanged is not None and not unchanged.is_active


def test_registration_trims_name_before_enforcing_length(client):
    response = client.post("/auth/register", json=VALID | {"display_name": " " * 120 + "Ana"})
    assert response.status_code == 202
    login = client.post(
        "/auth/token", data={"username": VALID["email"], "password": VALID["password"]}
    )
    me = client.get("/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]})
    assert me.json()["display_name"] == "Ana"


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "invalid"},
        {"display_name": "   "},
        {"display_name": "N" * 121},
        {"password": "short-secret"[:11]},
        {"password": "S" * 129},
        {"password": 123456789012},
        {"roles": ["admin"]},
        {"is_active": False},
    ],
)
def test_registration_rejects_invalid_data_without_echoing_password(client, changes):
    payload = VALID | changes
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422
    if isinstance(payload["password"], str):
        assert payload["password"] not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    assert (
        client.post(
            "/auth/token", data={"username": VALID["email"], "password": VALID["password"]}
        ).status_code
        == 401
    )

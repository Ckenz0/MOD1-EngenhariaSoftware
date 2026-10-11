from fastapi.testclient import TestClient

from mod1_auth.main import create_app


def test_user_and_token_survive_application_restart(settings, engine, user):
    with TestClient(create_app(settings)) as first:
        login = first.post(
            "/auth/token", data={"username": user.email, "password": "  password12345  "}
        )
        assert login.status_code == 200
        header = {"Authorization": "Bearer " + login.json()["access_token"]}
        first_identity = first.get("/auth/me", headers=header).json()
        first_kid = first.get("/.well-known/jwks.json").json()["keys"][0]["kid"]
    with TestClient(create_app(settings)) as second:
        response = second.get("/auth/me", headers=header)
        assert response.status_code == 200
        second_identity = response.json()
        second_kid = second.get("/.well-known/jwks.json").json()["keys"][0]["kid"]
        assert first_identity["id"] == second_identity["id"]
        assert first_kid == second_kid
        assert (
            second.post(
                "/auth/token", data={"username": user.email, "password": "  password12345  "}
            ).status_code
            == 200
        )

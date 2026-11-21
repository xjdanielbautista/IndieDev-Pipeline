"""Sesiones: listar, cerrar una, cerrar las demás y cerrar sesión."""

import jwt
import pytest

from app import main
from app.security import create_access_token


@pytest.fixture(autouse=True)
def no_mails(monkeypatch):
    monkeypatch.setattr(main, "send_email", lambda to, subject, text: None)


def register(client, username="sesiones"):
    response = client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "supersecreta1"},
    )
    assert response.status_code == 201


def login(client, username="sesiones", agent="pytest", password="supersecreta1"):
    response = client.post(
        "/api/auth/token",
        data={"username": username, "password": password},
        headers={"User-Agent": agent},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_login_creates_session_listed_with_current_flag(client):
    register(client)
    laptop = login(client, agent="Laptop Firefox")
    phone = login(client, agent="Celular Chrome")

    sessions = client.get("/api/auth/sessions", headers=laptop).json()
    assert len(sessions) == 2
    agents = {item["user_agent"]: item["current"] for item in sessions}
    assert agents == {"Laptop Firefox": True, "Celular Chrome": False}

    # Desde el celular, la actual es la del celular.
    from_phone = client.get("/api/auth/sessions", headers=phone).json()
    assert [item["user_agent"] for item in from_phone if item["current"]] == ["Celular Chrome"]


def test_revoke_one_session_invalidates_only_that_token(client):
    register(client)
    laptop = login(client, agent="Laptop")
    phone = login(client, agent="Celular")
    phone_id = next(
        item["id"] for item in client.get("/api/auth/sessions", headers=laptop).json() if not item["current"]
    )

    assert client.delete(f"/api/auth/sessions/{phone_id}", headers=laptop).status_code == 204
    assert client.get("/api/auth/me", headers=phone).status_code == 401
    assert client.get("/api/auth/me", headers=laptop).status_code == 200
    # Cerrarla otra vez: 404 con mensaje propio (no "Not Found").
    again = client.delete(f"/api/auth/sessions/{phone_id}", headers=laptop)
    assert again.status_code == 404 and again.json()["detail"] != "Not Found"


def test_cannot_revoke_someone_elses_session(client):
    register(client, "uno")
    register(client, "dos")
    uno = login(client, "uno")
    dos = login(client, "dos")
    dos_id = client.get("/api/auth/sessions", headers=dos).json()[0]["id"]

    assert client.delete(f"/api/auth/sessions/{dos_id}", headers=uno).status_code == 404
    assert client.get("/api/auth/me", headers=dos).status_code == 200


def test_revoke_other_sessions_keeps_current(client):
    register(client)
    keep = login(client, agent="Esta")
    others = [login(client, agent=f"Otra {n}") for n in range(3)]

    assert client.delete("/api/auth/sessions", headers=keep).status_code == 204
    assert all(client.get("/api/auth/me", headers=h).status_code == 401 for h in others)
    remaining = client.get("/api/auth/sessions", headers=keep).json()
    assert [(item["user_agent"], item["current"]) for item in remaining] == [("Esta", True)]


def test_logout_invalidates_token(client):
    register(client)
    headers = login(client)
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_change_password_closes_other_sessions_and_keeps_new_one(client):
    register(client)
    current = login(client, agent="Esta")
    other = login(client, agent="Otra")

    response = client.post(
        "/api/auth/password",
        json={"current_password": "supersecreta1", "new_password": "otraclave123"},
        headers=current,
    )
    assert response.status_code == 200
    new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=other).status_code == 401
    sessions = client.get("/api/auth/sessions", headers=new_headers).json()
    assert len(sessions) == 1 and sessions[0]["current"] is True


def test_forwarded_ip_is_recorded(client):
    register(client)
    response = client.post(
        "/api/auth/token",
        data={"username": "sesiones", "password": "supersecreta1"},
        headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
    )
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/auth/sessions", headers=headers).json()[0]["ip_address"] == "203.0.113.7"


def test_token_without_session_still_works(client):
    """Los tokens emitidos antes de esta versión (sin "sid") valen hasta que venzan."""
    register(client)
    user_id = client.get("/api/auth/me", headers=login(client)).json()["id"]
    legacy = {"Authorization": f"Bearer {create_access_token(user_id)}"}
    assert client.get("/api/auth/me", headers=legacy).status_code == 200
    assert client.get("/api/auth/sessions", headers=legacy).json()[0]["current"] is False


def test_forged_session_key_is_rejected(client):
    register(client)
    user_id = client.get("/api/auth/me", headers=login(client)).json()["id"]
    forged = {"Authorization": f"Bearer {create_access_token(user_id, 'no-existe')}"}
    assert client.get("/api/auth/me", headers=forged).status_code == 401


def test_session_key_of_other_user_is_rejected(client):
    register(client, "uno")
    register(client, "dos")
    uno = login(client, "uno")
    dos_id = client.get("/api/auth/me", headers=login(client, "dos")).json()["id"]
    sid = jwt.decode(uno["Authorization"].split()[1], options={"verify_signature": False})["sid"]
    mixed = {"Authorization": f"Bearer {create_access_token(dos_id, sid)}"}
    assert client.get("/api/auth/me", headers=mixed).status_code == 401


def test_delete_account_removes_sessions(client):
    register(client)
    headers = login(client)
    assert client.request("DELETE", "/api/auth/me", json={"password": "supersecreta1"}, headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401

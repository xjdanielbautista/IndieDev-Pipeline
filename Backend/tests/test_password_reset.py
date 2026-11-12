import re
from datetime import timedelta

import pytest

from app import main


@pytest.fixture
def outbox(monkeypatch):
    """Captura los correos en lugar de enviarlos."""
    sent = []
    monkeypatch.setattr(main, "send_email", lambda to, subject, text: sent.append((to, subject, text)))
    return sent


def request_reset(client, email):
    return client.post("/api/auth/password-reset/request", json={"email": email})


def token_from(outbox):
    return re.search(r"reset_token=([\w-]+)", outbox[-1][2]).group(1)


def confirm(client, token, new_password="nuevaClave123"):
    return client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "new_password": new_password}
    )


def try_login(client, username, password):
    return client.post("/api/auth/token", data={"username": username, "password": password})


def test_full_reset_flow(client, login, outbox):
    old_headers = login("olvidadizo")
    response = request_reset(client, "Olvidadizo@Example.com")
    assert response.status_code == 202
    assert len(outbox) == 1 and outbox[0][0] == "olvidadizo@example.com"
    assert "http://localhost:5173/?reset_token=" in outbox[0][2]

    assert confirm(client, token_from(outbox)).status_code == 204
    assert try_login(client, "olvidadizo", "supersecreta1").status_code == 401
    assert try_login(client, "olvidadizo", "nuevaClave123").status_code == 200
    # La sesión abierta antes del cambio queda cerrada.
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401


def test_unknown_email_gets_same_answer_and_no_email(client, login, outbox):
    login("alguien")
    known = request_reset(client, "alguien@example.com")
    unknown = request_reset(client, "nadie@example.com")
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(outbox) == 1


def test_token_is_single_use(client, login, outbox):
    login("unico")
    request_reset(client, "unico@example.com")
    token = token_from(outbox)
    assert confirm(client, token).status_code == 204
    assert confirm(client, token, "otraClave456").status_code == 400


def test_new_request_invalidates_previous_link(client, login, outbox):
    login("doble")
    request_reset(client, "doble@example.com")
    first = token_from(outbox)
    request_reset(client, "doble@example.com")
    second = token_from(outbox)
    assert confirm(client, first).status_code == 400
    assert confirm(client, second).status_code == 204


def test_expired_token_is_rejected(client, login, outbox, monkeypatch):
    login("tardio")
    request_reset(client, "tardio@example.com")
    token = token_from(outbox)
    later = main.utcnow() + timedelta(minutes=main.PASSWORD_RESET_MINUTES + 1)
    monkeypatch.setattr(main, "utcnow", lambda: later)
    assert confirm(client, token).status_code == 400


def test_invalid_token_and_short_password(client, outbox):
    assert confirm(client, "x" * 43).status_code == 400
    assert confirm(client, "x" * 43, "corta").status_code == 422


def test_requests_are_rate_limited(client, login, outbox):
    login("insistente")
    for _ in range(5):
        assert request_reset(client, "insistente@example.com").status_code == 202
    assert len(outbox) == main.MAX_RESET_REQUESTS


def test_reset_clears_login_lock(client, login, outbox):
    login("bloqueado")
    for _ in range(5):
        try_login(client, "bloqueado", "incorrecta")
    assert try_login(client, "bloqueado", "supersecreta1").status_code == 429
    request_reset(client, "bloqueado@example.com")
    assert confirm(client, token_from(outbox)).status_code == 204
    assert try_login(client, "bloqueado", "nuevaClave123").status_code == 200

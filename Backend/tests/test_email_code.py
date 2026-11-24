"""Confirmación de correo con código de 6 dígitos."""

import re
from datetime import timedelta

from sqlalchemy import update

from app import main
from app.models import EmailVerificationToken
from tests.test_account import mails, register, token_for, verify_token  # noqa: F401


def code_from(mails):
    return re.search(r"^\s+(\d{6})$", mails[-1][2], re.MULTILINE).group(1)


def confirm(client, email, code):
    return client.post("/api/auth/verify-email/code", json={"email": email, "code": code})


def wrong(code):
    return f"{(int(code) + 1) % 10**6:06d}"


def test_register_sends_code_in_subject_and_body(client, mails):
    assert register(client, "codigo").status_code == 201
    to, subject, text = mails[0]
    code = code_from(mails)
    assert to == "codigo@example.com"
    assert subject.startswith(code)
    assert "verify_token=" in text  # el enlace sigue llegando


def test_code_confirms_email_once(client, mails):
    register(client, "unavez")
    _, headers = token_for(client, "unavez")
    code = code_from(mails)
    assert confirm(client, "UnaVez@Example.com", code).status_code == 204
    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is True
    # Ya confirmado: repetir no falla.
    assert confirm(client, "unavez@example.com", code).status_code == 204


def test_wrong_code_and_lockout(client, mails):
    register(client, "fuerza")
    code = code_from(mails)
    for _ in range(main.MAX_CODE_ATTEMPTS - 1):
        response = confirm(client, "fuerza@example.com", wrong(code))
        assert response.status_code == 400
    assert confirm(client, "fuerza@example.com", wrong(code)).status_code == 429
    # Tras el bloqueo ni el código correcto sirve: hay que pedir otro.
    assert confirm(client, "fuerza@example.com", code).status_code == 400

    client.post("/api/auth/verify-email/resend", json={"email": "fuerza@example.com"})
    assert confirm(client, "fuerza@example.com", code_from(mails)).status_code == 204


def test_only_latest_code_works_but_old_link_still_does(client, mails):
    register(client, "reenvio")
    first_code, first_link = code_from(mails), verify_token(mails)
    client.post("/api/auth/verify-email/resend", json={"email": "reenvio@example.com"})
    second_code = code_from(mails)
    if first_code != second_code:
        assert confirm(client, "reenvio@example.com", first_code).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": first_link}).status_code == 204


def test_expired_code_is_rejected(client, mails):
    register(client, "vencido")
    code = code_from(mails)
    db = next(client.app.dependency_overrides[main.get_db]())
    db.execute(update(EmailVerificationToken).values(code_expires_at=main.utcnow() - timedelta(minutes=1)))
    db.commit()
    db.close()
    assert confirm(client, "vencido@example.com", code).status_code == 400


def test_unknown_email_and_bad_format(client, mails):
    assert confirm(client, "nadie@example.com", "123456").status_code == 400
    assert confirm(client, "nadie@example.com", "12ab56").status_code == 422


def test_required_verification_then_code_allows_login(client, mails, monkeypatch):
    monkeypatch.setenv("REQUIRE_EMAIL_VERIFICATION", "true")
    register(client, "requerido")
    response, _ = token_for(client, "requerido")
    assert response.status_code == 403
    assert "código" in response.json()["detail"]
    assert confirm(client, "requerido@example.com", code_from(mails)).status_code == 204
    response, _ = token_for(client, "requerido")
    assert response.status_code == 200

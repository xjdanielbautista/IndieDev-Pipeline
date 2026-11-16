import re

import pytest

from app import main


@pytest.fixture
def mails(monkeypatch):
    sent = []
    monkeypatch.setattr(main, "send_email", lambda to, subject, text: sent.append((to, subject, text)))
    return sent


def verify_token(mails):
    return re.search(r"verify_token=([\w-]+)", mails[-1][2]).group(1)


def register(client, username, password="supersecreta1"):
    return client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": password},
    )


def token_for(client, username, password="supersecreta1"):
    response = client.post("/api/auth/token", data={"username": username, "password": password})
    return response, {"Authorization": f"Bearer {response.json().get('access_token')}"}


# ---------- Confirmación de correo ----------


def test_register_sends_verification_and_link_confirms(client, mails):
    assert register(client, "nuevo").status_code == 201
    assert mails[0][0] == "nuevo@example.com" and "verify_token=" in mails[0][2]
    _, headers = token_for(client, "nuevo")
    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is False
    assert client.post("/api/auth/verify-email", json={"token": verify_token(mails)}).status_code == 204
    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is True
    # El enlace es de un solo uso.
    assert client.post("/api/auth/verify-email", json={"token": verify_token(mails)}).status_code == 400


def test_login_requires_verification_only_when_enabled(client, mails, monkeypatch):
    register(client, "pendiente")
    assert token_for(client, "pendiente")[0].status_code == 200
    monkeypatch.setenv("REQUIRE_EMAIL_VERIFICATION", "true")
    response, _ = token_for(client, "pendiente")
    assert response.status_code == 403 and "Confirma tu correo" in response.json()["detail"]
    client.post("/api/auth/verify-email", json={"token": verify_token(mails)})
    assert token_for(client, "pendiente")[0].status_code == 200


def test_resend_is_generic_and_rate_limited(client, mails):
    register(client, "reenvio")
    unknown = client.post("/api/auth/verify-email/resend", json={"email": "nadie@example.com"})
    known = client.post("/api/auth/verify-email/resend", json={"email": "reenvio@example.com"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    for _ in range(5):
        client.post("/api/auth/verify-email/resend", json={"email": "reenvio@example.com"})
    assert len(mails) == main.MAX_VERIFICATION_EMAILS


def test_password_reset_also_verifies_email(client, mails):
    register(client, "olvido")
    client.post("/api/auth/password-reset/request", json={"email": "olvido@example.com"})
    token = re.search(r"reset_token=([\w-]+)", mails[-1][2]).group(1)
    client.post("/api/auth/password-reset/confirm", json={"token": token, "new_password": "otraclave123"})
    _, headers = token_for(client, "olvido", "otraclave123")
    assert client.get("/api/auth/me", headers=headers).json()["email_verified"] is True


# ---------- Cambiar contraseña ----------


def test_change_password_keeps_this_session_and_closes_the_others(client, mails):
    register(client, "cambia")
    _, old_headers = token_for(client, "cambia")
    bad = client.post(
        "/api/auth/password", json={"current_password": "incorrecta", "new_password": "nuevaclave123"}, headers=old_headers
    )
    assert bad.status_code == 400
    response = client.post(
        "/api/auth/password",
        json={"current_password": "supersecreta1", "new_password": "nuevaclave123"},
        headers=old_headers,
    )
    assert response.status_code == 200
    new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    assert token_for(client, "cambia", "nuevaclave123")[0].status_code == 200


# ---------- Eliminar cuenta ----------


def test_delete_account_removes_user_but_keeps_their_work(client, mails, login):
    owner = login("dueno")
    tenant = client.post("/api/tenants", json={"name": "S", "slug": "s-del"}, headers=owner).json()
    project = client.post(f"/api/tenants/{tenant['id']}/projects", json={"name": "P"}, headers=owner).json()
    base = f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets"
    dev = login("dev")
    dev_id = client.get("/api/auth/me", headers=dev).json()["id"]
    client.post(f"/api/tenants/{tenant['id']}/members", json={"identifier": "dev", "role": "developer"}, headers=owner)
    asset = client.post(
        base,
        json={"original_name": "a.cs", "storage_key": "a.cs", "category": "code", "assigned_user_ids": [dev_id]},
        headers=owner,
    ).json()
    client.patch(f"{base}/{asset['id']}/lock", json={}, headers=dev)
    client.post(f"{base}/{asset['id']}/comments", json={"body": "listo"}, headers=dev)

    assert client.request("DELETE", "/api/auth/me", json={"password": "mala"}, headers=dev).status_code == 400
    assert client.request("DELETE", "/api/auth/me", json={"password": "supersecreta1"}, headers=dev).status_code == 204

    assert client.get("/api/auth/me", headers=dev).status_code == 401
    assert token_for(client, "dev")[0].status_code == 401
    members = client.get(f"/api/tenants/{tenant['id']}/members", headers=owner).json()
    assert [m["username"] for m in members] == ["dueno"]
    updated = client.get(f"{base}/{asset['id']}", headers=owner).json()
    assert updated["locked_by_user_id"] is None and updated["assigned_user_ids"] == []
    comments = client.get(f"{base}/{asset['id']}/comments", headers=owner).json()
    assert comments[0]["body"] == "listo" and comments[0]["user"] is None
    activity = client.get(f"/api/tenants/{tenant['id']}/activity", headers=owner).json()
    assert activity[0]["action"] == "account_deleted"
    # El nombre queda libre para registrarse de nuevo.
    assert register(client, "dev").status_code == 201


def test_owner_cannot_delete_account_while_owning_studios(client, mails, login):
    owner = login("dueno2")
    client.post("/api/tenants", json={"name": "Mi Estudio", "slug": "mi-estudio"}, headers=owner)
    response = client.request("DELETE", "/api/auth/me", json={"password": "supersecreta1"}, headers=owner)
    assert response.status_code == 409 and "Mi Estudio" in response.json()["detail"]


# ---------- Superadmin ----------


@pytest.fixture
def superadmin(client, mails, monkeypatch):
    monkeypatch.setenv("SUPERADMIN_EMAILS", "jefe@example.com, otro@example.com")
    register(client, "jefe")
    _, headers = token_for(client, "jefe")
    return headers


def test_superadmin_needs_verified_email(client, mails, superadmin):
    assert client.get("/api/auth/me", headers=superadmin).json()["is_superadmin"] is False
    assert client.get("/api/admin/users", headers=superadmin).status_code == 403
    client.post("/api/auth/verify-email", json={"token": verify_token(mails)})
    assert client.get("/api/auth/me", headers=superadmin).json()["is_superadmin"] is True
    assert client.get("/api/admin/users", headers=superadmin).status_code == 200


def test_superadmin_lists_and_deletes(client, mails, superadmin, login):
    client.post("/api/auth/verify-email", json={"token": verify_token(mails)})
    owner = login("dueno3")
    tenant = client.post("/api/tenants", json={"name": "Borrable", "slug": "borrable"}, headers=owner).json()
    regular = login("normal")
    assert client.get("/api/admin/users", headers=regular).status_code == 403
    assert client.delete(f"/api/admin/tenants/{tenant['id']}", headers=regular).status_code == 403

    users = {u["username"]: u for u in client.get("/api/admin/users", headers=superadmin).json()}
    assert users["dueno3"]["owned_studios"] == ["Borrable"] and users["jefe"]["is_superadmin"] is True
    tenants = client.get("/api/admin/tenants", headers=superadmin).json()
    assert tenants[0]["owner_username"] == "dueno3" and tenants[0]["member_count"] == 1

    # No se puede borrar a un dueño sin borrar antes su estudio.
    assert client.delete(f"/api/admin/users/{users['dueno3']['id']}", headers=superadmin).status_code == 409
    assert client.delete(f"/api/admin/tenants/{tenant['id']}", headers=superadmin).status_code == 204
    assert client.delete(f"/api/admin/users/{users['dueno3']['id']}", headers=superadmin).status_code == 204
    assert client.delete(f"/api/admin/users/{users['jefe']['id']}", headers=superadmin).status_code == 400
    remaining = {u["username"] for u in client.get("/api/admin/users", headers=superadmin).json()}
    assert remaining == {"jefe", "normal"}

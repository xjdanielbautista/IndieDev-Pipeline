from datetime import timedelta

from app import main


def studio(client, headers, slug="studio-a"):
    tenant = client.post("/api/tenants", json={"name": slug.title(), "slug": slug}, headers=headers).json()
    project = client.post(
        f"/api/tenants/{tenant['id']}/projects", json={"name": "Juego"}, headers=headers
    ).json()
    asset = client.post(
        f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets",
        json={"original_name": "hero.png", "storage_key": "hero.png", "category": "art"},
        headers=headers,
    ).json()
    return tenant, project, asset


def add_member(client, tenant_id, owner, username, role):
    client.post(
        f"/api/tenants/{tenant_id}/members", json={"identifier": username, "role": role}, headers=owner
    )


def try_login(client, username, password):
    return client.post("/api/auth/token", data={"username": username, "password": password})


# ---------- Límite de intentos de login ----------

def test_login_locks_after_five_failures(client, login, monkeypatch):
    login("victima")
    for _ in range(4):
        assert try_login(client, "victima", "incorrecta").status_code == 401
    fifth = try_login(client, "victima", "incorrecta")
    assert fifth.status_code == 429
    assert "Retry-After" in fifth.headers
    # Bloqueado incluso con la contraseña correcta.
    assert try_login(client, "victima", "supersecreta1").status_code == 429

    # Pasado el bloqueo, la contraseña correcta vuelve a funcionar.
    real_now = main.utcnow()
    monkeypatch.setattr(main, "utcnow", lambda: real_now + timedelta(minutes=16))
    assert try_login(client, "victima", "supersecreta1").status_code == 200


def test_successful_login_resets_failed_count(client, login):
    login("olvidadizo")
    for _ in range(3):
        try_login(client, "olvidadizo", "incorrecta")
    assert try_login(client, "olvidadizo", "supersecreta1").status_code == 200
    for _ in range(4):
        assert try_login(client, "olvidadizo", "incorrecta").status_code == 401


def test_unknown_user_is_also_throttled(client):
    for _ in range(4):
        assert try_login(client, "noexiste", "x").status_code == 401
    assert try_login(client, "noexiste", "x").status_code == 429


# ---------- Bitácora ----------

def test_activity_log_records_admin_actions_for_managers_only(client, login):
    owner = login("dueno")
    dev = login("dev")
    tenant, project, asset = studio(client, owner)
    add_member(client, tenant["id"], owner, "dev", "developer")

    activity = client.get(f"/api/tenants/{tenant['id']}/activity", headers=owner)
    assert activity.status_code == 200
    actions = [entry["action"] for entry in activity.json()]
    assert actions == ["member_added", "asset_created", "project_created", "tenant_created"]
    assert activity.json()[0]["actor_username"] == "dueno"
    assert "dev como developer" in activity.json()[0]["summary"]

    assert client.get(f"/api/tenants/{tenant['id']}/activity", headers=dev).status_code == 403


def test_activity_log_is_isolated_per_tenant(client, login):
    owner_a = login("duenoa")
    owner_b = login("duenob")
    tenant_a, _, _ = studio(client, owner_a, "estudio-a")
    studio(client, owner_b, "estudio-b")
    assert client.get(f"/api/tenants/{tenant_a['id']}/activity", headers=owner_b).status_code == 403


# ---------- Editar / eliminar estudio ----------

def test_update_tenant_name_and_slug(client, login):
    owner = login("dueno")
    dev = login("dev")
    tenant, _, _ = studio(client, owner, "original")
    studio(client, owner, "ocupado")
    add_member(client, tenant["id"], owner, "dev", "developer")
    url = f"/api/tenants/{tenant['id']}"

    assert client.patch(url, json={"name": "X"}, headers=dev).status_code == 403
    assert client.patch(url, json={"slug": "ocupado"}, headers=owner).status_code == 409
    updated = client.patch(url, json={"name": "Nuevo Nombre", "slug": "nuevo"}, headers=owner)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Nuevo Nombre" and updated.json()["slug"] == "nuevo"
    assert client.get(f"{url}/activity", headers=owner).json()[0]["action"] == "tenant_updated"


def test_delete_tenant_requires_owner_and_confirmation_and_cascades(client, login):
    owner = login("dueno")
    admin = login("admin")
    other = login("otro")
    tenant, project, asset = studio(client, owner, "borrame")
    other_tenant, other_project, _ = studio(client, other, "intacto")
    add_member(client, tenant["id"], owner, "admin", "admin")
    url = f"/api/tenants/{tenant['id']}"

    assert client.delete(f"{url}?confirm=borrame", headers=admin).status_code == 403
    assert client.delete(f"{url}?confirm=otra-cosa", headers=owner).status_code == 400
    assert client.delete(f"{url}?confirm=borrame", headers=owner).status_code == 204

    assert client.get("/api/tenants", headers=owner).json() == []
    assert client.get(f"{url}/projects", headers=owner).status_code == 403
    # El otro estudio no se toca.
    assert client.get(f"/api/tenants/{other_tenant['id']}/projects/{other_project['id']}/assets", headers=other).status_code == 200


# ---------- Editar / eliminar proyectos y tareas ----------

def test_update_and_delete_project(client, login):
    owner = login("dueno")
    artist = login("artista")
    tenant, project, asset = studio(client, owner)
    add_member(client, tenant["id"], owner, "artista", "artist")
    url = f"/api/tenants/{tenant['id']}/projects/{project['id']}"

    assert client.patch(url, json={"name": "X"}, headers=artist).status_code == 403
    renamed = client.patch(url, json={"name": "Juego 2", "description": "Secuela"}, headers=owner)
    assert renamed.status_code == 200 and renamed.json()["name"] == "Juego 2"

    assert client.delete(url, headers=artist).status_code == 403
    assert client.delete(url, headers=owner).status_code == 204
    assert client.get(f"{url}/assets", headers=owner).status_code == 404
    assert client.get(f"/api/tenants/{tenant['id']}/projects", headers=owner).json() == []
    assert client.get(f"/api/tenants/{tenant['id']}/activity", headers=owner).json()[0]["action"] == "project_deleted"


def test_delete_asset(client, login):
    owner = login("dueno")
    dev = login("dev")
    intruder = login("intruso")
    tenant, project, asset = studio(client, owner)
    studio(client, intruder, "otro-estudio")
    add_member(client, tenant["id"], owner, "dev", "developer")
    url = f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets/{asset['id']}"

    assert client.delete(url, headers=intruder).status_code == 403
    assert client.delete(url, headers=dev).status_code == 403
    assert client.delete(url, headers=owner).status_code == 204
    assert client.delete(url, headers=owner).status_code == 404
    assert client.get(f"{url}/history", headers=owner).status_code == 404

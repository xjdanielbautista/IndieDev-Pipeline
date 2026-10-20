import pytest


@pytest.fixture
def studio(client, login):
    """Estudio con dueño, admin, developer, artista y tester, más un proyecto y dos tareas."""
    headers = {name: login(name) for name in ["owner", "admin", "dev", "artist", "tester"]}
    tenant = client.post("/api/tenants", json={"name": "Studio", "slug": "studio"}, headers=headers["owner"]).json()
    tid = tenant["id"]
    for name, role in [("admin", "admin"), ("dev", "developer"), ("artist", "artist"), ("tester", "tester")]:
        response = client.post(
            f"/api/tenants/{tid}/members", json={"identifier": f"{name}@example.com", "role": role}, headers=headers["owner"]
        )
        assert response.status_code == 201, response.text
    project = client.post(f"/api/tenants/{tid}/projects", json={"name": "Game"}, headers=headers["owner"]).json()
    base = f"/api/tenants/{tid}/projects/{project['id']}/assets"
    code = client.post(base, json={"original_name": "dash", "storage_key": "k1", "category": "code"}, headers=headers["owner"]).json()
    art = client.post(base, json={"original_name": "sprite", "storage_key": "k2", "category": "art"}, headers=headers["owner"]).json()
    return {"h": headers, "tid": tid, "base": base, "code": code, "art": art}


def move(client, s, who, asset, status):
    return client.patch(f"{s['base']}/{asset['id']}", json={"status": status}, headers=s["h"][who])


def test_members_list_includes_roles(client, studio):
    members = client.get(f"/api/tenants/{studio['tid']}/members", headers=studio["h"]["dev"]).json()
    assert {m["username"]: m["role"] for m in members} == {
        "admin": "admin", "artist": "artist", "dev": "developer", "owner": "owner", "tester": "tester",
    }


def test_member_management_rules(client, studio, login):
    tid, h = studio["tid"], studio["h"]
    login("newbie")
    members = {m["username"]: m["id"] for m in client.get(f"/api/tenants/{tid}/members", headers=h["owner"]).json()}
    url = f"/api/tenants/{tid}/members"

    # Solo dueño/admin agregan; nadie puede asignar "owner"; solo el dueño nombra admins.
    assert client.post(url, json={"identifier": "newbie", "role": "tester"}, headers=h["dev"]).status_code == 403
    assert client.post(url, json={"identifier": "newbie", "role": "owner"}, headers=h["owner"]).status_code == 403
    assert client.post(url, json={"identifier": "newbie", "role": "admin"}, headers=h["admin"]).status_code == 403
    assert client.post(url, json={"identifier": "nadie", "role": "tester"}, headers=h["owner"]).status_code == 404
    assert client.post(url, json={"identifier": "newbie", "role": "artist"}, headers=h["admin"]).status_code == 201
    assert client.post(url, json={"identifier": "newbie", "role": "artist"}, headers=h["admin"]).status_code == 409

    # Cambiar rol y quitar
    assert client.patch(f"{url}/{members['dev']}", json={"role": "tester"}, headers=h["admin"]).json()["role"] == "tester"
    assert client.patch(f"{url}/{members['owner']}", json={"role": "tester"}, headers=h["admin"]).status_code == 403
    assert client.delete(f"{url}/{members['admin']}", headers=h["admin"]).status_code == 403
    assert client.delete(f"{url}/{members['admin']}", headers=h["owner"]).status_code == 204
    assert client.get(f"/api/tenants/{tid}/projects", headers=h["admin"]).status_code == 403


def test_removing_member_clears_assignments_and_locks(client, studio):
    tid, h, base, art = studio["tid"], studio["h"], studio["base"], studio["art"]
    members = {m["username"]: m["id"] for m in client.get(f"/api/tenants/{tid}/members", headers=h["owner"]).json()}
    client.patch(f"{base}/{art['id']}", json={"assigned_user_ids": [members["artist"]]}, headers=h["owner"])
    client.patch(f"{base}/{art['id']}/lock", json={}, headers=h["artist"])

    client.delete(f"/api/tenants/{tid}/members/{members['artist']}", headers=h["owner"])

    asset = client.get(f"{base}/{art['id']}", headers=h["owner"]).json()
    assert asset["assigned_user_ids"] == []
    assert asset["locked_by_user_id"] is None


def test_only_managers_create_projects_and_tasks(client, studio):
    tid, h, base = studio["tid"], studio["h"], studio["base"]
    assert client.post(f"/api/tenants/{tid}/projects", json={"name": "X"}, headers=h["dev"]).status_code == 403
    assert client.post(base, json={"original_name": "a", "storage_key": "k"}, headers=h["artist"]).status_code == 403
    assert client.post(base, json={"original_name": "a", "storage_key": "k"}, headers=h["admin"]).status_code == 201


def test_role_based_moves(client, studio):
    code, art = studio["code"], studio["art"]
    assert move(client, studio, "dev", code, "in_progress").status_code == 200
    assert move(client, studio, "dev", art, "in_progress").status_code == 403
    assert move(client, studio, "artist", art, "in_progress").status_code == 200
    assert move(client, studio, "artist", code, "review").status_code == 403
    # tester: solo desde/hacia revisión
    assert move(client, studio, "tester", code, "review").status_code == 403
    assert move(client, studio, "dev", code, "review").status_code == 200
    assert move(client, studio, "tester", code, "done").status_code == 200
    assert move(client, studio, "tester", code, "review").status_code == 200
    assert move(client, studio, "tester", code, "in_progress").status_code == 200
    # dueño mueve lo que sea
    assert move(client, studio, "owner", art, "done").status_code == 200


def test_only_managers_change_category_or_assignees(client, studio):
    base, h, code = studio["base"], studio["h"], studio["code"]
    assert client.patch(f"{base}/{code['id']}", json={"category": "art"}, headers=h["dev"]).status_code == 403
    assert client.patch(f"{base}/{code['id']}", json={"assigned_user_ids": []}, headers=h["dev"]).status_code == 403
    assert client.patch(f"{base}/{code['id']}", json={"category": "art"}, headers=h["admin"]).status_code == 200


def test_restricted_mode_still_applies_but_managers_bypass(client, studio):
    tid, h, base, code = studio["tid"], studio["h"], studio["base"], studio["code"]
    members = {m["username"]: m["id"] for m in client.get(f"/api/tenants/{tid}/members", headers=h["owner"]).json()}
    client.patch(
        f"{base}/{code['id']}",
        json={"assignment_mode": "restricted", "assigned_user_ids": [members["admin"]]},
        headers=h["owner"],
    )
    assert move(client, studio, "dev", code, "in_progress").status_code == 403
    assert move(client, studio, "owner", code, "in_progress").status_code == 200


def test_lock_rules_and_manager_force_unlock(client, studio):
    h, base, code, art = studio["h"], studio["base"], studio["code"], studio["art"]
    assert client.patch(f"{base}/{art['id']}/lock", json={}, headers=h["dev"]).status_code == 403
    assert client.patch(f"{base}/{art['id']}/lock", json={}, headers=h["tester"]).status_code == 403
    assert client.patch(f"{base}/{code['id']}/lock", json={}, headers=h["dev"]).status_code == 200
    assert client.delete(f"{base}/{code['id']}/lock", headers=h["artist"]).status_code == 409
    assert client.delete(f"{base}/{code['id']}/lock", headers=h["admin"]).status_code == 200
    history = client.get(f"{base}/{code['id']}/history", headers=h["owner"]).json()
    assert history[0]["action"] == "unlocked" and history[0]["previous_value"] == "dev"


def test_build_permissions(client, studio):
    tid, h = studio["tid"], studio["h"]
    url = studio["base"].replace("/assets", "/builds")
    assert client.post(url, json={"version": "v1"}, headers=h["artist"]).status_code == 403
    assert client.post(url, json={"version": "v1"}, headers=h["dev"]).status_code == 201
    assert client.get(url, headers=h["artist"]).status_code == 200
    assert tid

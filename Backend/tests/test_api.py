def test_tenant_scoping_and_kanban_task(client, login):
    one = login("one")
    two = login("two")
    first_tenant = client.post("/api/tenants", json={"name": "Studio One", "slug": "studio-one"}, headers=one).json()
    second_tenant = client.post("/api/tenants", json={"name": "Studio Two", "slug": "studio-two"}, headers=two).json()
    project = client.post(
        f"/api/tenants/{first_tenant['id']}/projects",
        json={"name": "My Game", "description": "Prototype"},
        headers=one,
    ).json()

    task_response = client.post(
        f"/api/tenants/{first_tenant['id']}/projects/{project['id']}/tasks",
        json={"title": "Create player controller", "stage": "alpha", "area": "programming"},
        headers=one,
    )

    assert task_response.status_code == 201
    assert task_response.json()["stage"] == "alpha"
    assert client.get(f"/api/tenants/{second_tenant['id']}/projects", headers=two).json() == []
    assert client.get(
        f"/api/tenants/{second_tenant['id']}/projects/{project['id']}/tasks", headers=two
    ).status_code == 404
    # Un usuario de otro estudio no puede ver los proyectos del primero.
    assert client.get(f"/api/tenants/{first_tenant['id']}/projects", headers=two).status_code == 403


def test_asset_lock_requires_tenant_membership(client, login):
    owner = login("owner")
    outsider = login("outsider")
    tenant = client.post("/api/tenants", json={"name": "Studio", "slug": "studio"}, headers=owner).json()
    project = client.post(f"/api/tenants/{tenant['id']}/projects", json={"name": "Game"}, headers=owner).json()
    asset = client.post(
        f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets",
        json={"original_name": "model.fbx", "storage_key": "assets/model.fbx"},
        headers=owner,
    ).json()
    lock_url = f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets/{asset['id']}/lock"

    locked = client.patch(lock_url, json={}, headers=owner)
    rejected = client.patch(lock_url, json={}, headers=outsider)

    assert locked.status_code == 200
    assert locked.json()["locked_by_user_id"] == tenant["owner_user_id"]
    assert rejected.status_code == 403


def test_storage_key_is_prefixed_by_tenant(client, login):
    owner = login("prefixowner")
    tenant = client.post("/api/tenants", json={"name": "Prefijo", "slug": "prefijo"}, headers=owner).json()
    project = client.post(f"/api/tenants/{tenant['id']}/projects", json={"name": "P"}, headers=owner).json()
    asset = client.post(
        f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets",
        json={"original_name": "hero.png", "storage_key": "../../tenants/999/robado.png"},
        headers=owner,
    ).json()
    assert asset["storage_key"] == f"tenants/{tenant['id']}/projects/{project['id']}/tenants/999/robado.png"

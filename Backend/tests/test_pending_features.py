import hashlib
import hmac
import json



def setup_project(client, login, slug="feature-studio"):
    headers = login("owner")
    tenant = client.post("/api/tenants", json={"name": "Feature Studio", "slug": slug}, headers=headers)
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]
    project = client.post(
        f"/api/tenants/{tenant_id}/projects",
        json={"name": "Feature Project"},
        headers=headers,
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    asset = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets",
        json={
            "original_name": "engine.py",
            "storage_key": "studio/engine.py",
            "category": "code",
            "status": "backlog",
            "assignment_mode": "open",
            "assigned_user_ids": [],
        },
        headers=headers,
    )
    assert asset.status_code == 201
    return tenant_id, project_id, asset.json()["id"], headers


def test_comments_create_list_and_delete(client, login):
    tenant_id, project_id, asset_id, headers = setup_project(client, login)
    base = f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}"

    created = client.post(f"{base}/comments", json={"body": "  Ya quedó el código  "}, headers=headers)
    assert created.status_code == 201
    assert created.json()["body"] == "Ya quedó el código"
    assert created.json()["user"]["username"] == "owner"

    comments = client.get(f"{base}/comments", headers=headers)
    assert comments.status_code == 200
    assert len(comments.json()) == 1

    deleted = client.delete(f"{base}/comments/{created.json()['id']}", headers=headers)
    assert deleted.status_code == 204

    missing = client.delete(f"{base}/comments/999999", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Comentario no encontrado"


def test_notifications_list_and_mark_read(client, login):
    tenant_id, project_id, asset_id, headers = setup_project(client, login)
    base = f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}"

    created = client.post(f"{base}/comments", json={"body": "Comentario del dueño"}, headers=headers)
    assert created.status_code == 201

    result = client.get("/api/notifications?limit=30", headers=headers)
    assert result.status_code == 200
    if result.json():
        marked = client.post("/api/notifications/read", json={"ids": [result.json()[0]["id"]]}, headers=headers)
        assert marked.status_code == 204


def test_internal_error_has_json_and_cors_headers(client):
    from fastapi.testclient import TestClient
    from app import main

    async def fail_for_test():
        raise RuntimeError("error temporal de prueba")

    main.app.add_api_route("/__test_internal_error", fail_for_test, methods=["GET"])
    with TestClient(main.app, raise_server_exceptions=False) as error_client:
        response = error_client.get(
            "/__test_internal_error",
            headers={"Origin": "http://localhost:5173"},
        )
    assert response.status_code == 500
    assert response.json() == {"detail": "Error interno del servidor"}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

    main.app.router.routes[:] = [
        route for route in main.app.router.routes
        if getattr(route, "path", None) != "/__test_internal_error"
    ]


def test_github_webhook_signature_and_commits(client, login):
    tenant_id, project_id, asset_id, headers = setup_project(client, login, "github-studio")

    connected = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/github",
        json={"github_repo": "owner/repo"},
        headers=headers,
    )
    assert connected.status_code == 200
    secret = connected.json()["secret"]

    payload = {
        "commits": [{
            "id": "f7a9c2b1d3e4",
            "message": "Agrega dash aéreo #" + str(asset_id),
            "author": {"name": "Alex"},
            "url": "https://github.com/owner/repo/commit/f7a9c2b1d3e4",
            "timestamp": "2026-10-20T08:15:00Z",
        }]
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    accepted = client.post(
        f"/api/webhooks/github/{project_id}",
        content=raw,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )
    assert accepted.status_code == 204

    commits = client.get(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/commits",
        headers=headers,
    )
    assert commits.status_code == 200
    assert commits.json()[0]["author_name"] == "Alex"

    rejected = client.post(
        f"/api/webhooks/github/{project_id}",
        content=raw,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=incorrecta", "Content-Type": "application/json"},
    )
    assert rejected.status_code == 401

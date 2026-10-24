from io import BytesIO

from app.models import AssetCategory, MemberRole


def create_asset(client, login, tmp_path):
    headers = login("owner")
    tenant_response = client.post(
        "/api/tenants",
        json={"name": "File Studio", "slug": "file-studio"},
        headers=headers,
    )
    tenant_id = tenant_response.json()["id"]
    project_response = client.post(
        f"/api/tenants/{tenant_id}/projects",
        json={"name": "Asset Project"},
        headers=headers,
    )
    project_id = project_response.json()["id"]
    asset_response = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets",
        json={
            "original_name": "hero.png",
            "storage_key": "file-studio/asset-project/hero.png",
            "category": "art",
            "status": "backlog",
            "assignment_mode": "open",
            "assigned_user_ids": [],
        },
        headers=headers,
    )
    asset_id = asset_response.json()["id"]
    return tenant_id, project_id, asset_id, headers


def test_upload_requires_lock(client, login):
    tenant_id, project_id, asset_id, headers = create_asset(client, login, None)
    response = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file",
        files={"file": ("hero.png", BytesIO(b"image-data"), "image/png")},
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Bloquea el archivo antes de subir una nueva versión"


def test_upload_and_download_local(client, login, monkeypatch, tmp_path):
    monkeypatch.setenv("ASSET_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    tenant_id, project_id, asset_id, headers = create_asset(client, login, tmp_path)

    lock_response = client.patch(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/lock",
        json={},
        headers=headers,
    )
    assert lock_response.status_code == 200

    upload_response = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file",
        files={"file": ("hero.png", BytesIO(b"new-image-data"), "image/png")},
        headers=headers,
    )
    assert upload_response.status_code == 200
    assert upload_response.json()["file_size"] == 14
    assert upload_response.json()["content_type"] == "image/png"
    assert upload_response.json()["file_uploaded_at"] is not None

    download_response = client.get(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file",
        headers=headers,
    )
    assert download_response.status_code == 200
    assert download_response.content == b"new-image-data"


def test_download_before_upload_is_specific_404(client, login):
    tenant_id, project_id, asset_id, headers = create_asset(client, login, None)
    response = client.get(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Este asset todavía no tiene archivo"


def test_upload_size_limit(client, login, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    tenant_id, project_id, asset_id, headers = create_asset(client, login, None)
    lock_response = client.patch(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/lock",
        json={},
        headers=headers,
    )
    assert lock_response.status_code == 200

    response = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/file",
        files={"file": ("large.bin", BytesIO(b"x" * (1024 * 1024 + 1)), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 413

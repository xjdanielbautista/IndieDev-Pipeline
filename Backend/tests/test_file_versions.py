from io import BytesIO

import pytest


@pytest.fixture
def asset(client, login, monkeypatch, tmp_path):
    monkeypatch.setenv("ASSET_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    headers = login("owner")
    tenant = client.post("/api/tenants", json={"name": "V", "slug": "v-studio"}, headers=headers).json()
    project = client.post(f"/api/tenants/{tenant['id']}/projects", json={"name": "P"}, headers=headers).json()
    base = f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets"
    created = client.post(
        base, json={"original_name": "player.cs", "storage_key": "player.cs", "category": "code"}, headers=headers
    ).json()
    url = f"{base}/{created['id']}"
    assert client.patch(f"{url}/lock", json={}, headers=headers).status_code == 200
    return {"url": url, "h": headers, "tid": tenant["id"], "tmp": tmp_path}


def upload(client, a, content, name="player.cs", ctype="text/plain"):
    return client.post(f"{a['url']}/file", files={"file": (name, BytesIO(content), ctype)}, headers=a["h"])


def test_each_upload_creates_a_version_and_keeps_the_old_file(client, asset):
    assert upload(client, asset, b"v1").status_code == 200
    assert upload(client, asset, b"version 2").status_code == 200
    versions = client.get(f"{asset['url']}/versions", headers=asset["h"]).json()
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[0]["uploaded_by"]["username"] == "owner"
    assert versions[1]["file_size"] == 2
    # La versión actual es la última y la anterior sigue disponible.
    assert client.get(f"{asset['url']}/file", headers=asset["h"]).content == b"version 2"
    old = client.get(f"{asset['url']}/versions/{versions[1]['id']}/file", headers=asset["h"])
    assert old.status_code == 200 and old.content == b"v1"


def test_preview_returns_content_with_safe_headers(client, asset):
    upload(client, asset, b"<script>alert(1)</script>", name="x.html", ctype="text/html")
    response = client.get(f"{asset['url']}/file/preview", headers=asset["h"])
    assert response.status_code == 200
    assert response.content == b"<script>alert(1)</script>"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in response.headers["content-security-policy"]
    versions = client.get(f"{asset['url']}/versions", headers=asset["h"]).json()
    assert client.get(f"{asset['url']}/versions/{versions[0]['id']}/preview", headers=asset["h"]).status_code == 200


def test_preview_size_limit(client, asset, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "PREVIEW_MAX_BYTES", 4)
    upload(client, asset, b"12345")
    assert client.get(f"{asset['url']}/file/preview", headers=asset["h"]).status_code == 413


def test_preview_without_file_is_404(client, asset):
    assert client.get(f"{asset['url']}/file/preview", headers=asset["h"]).status_code == 404


def test_restore_creates_new_version_with_old_content(client, asset):
    upload(client, asset, b"bueno")
    upload(client, asset, b"roto")
    v1 = client.get(f"{asset['url']}/versions", headers=asset["h"]).json()[1]
    restored = client.post(f"{asset['url']}/versions/{v1['id']}/restore", headers=asset["h"])
    assert restored.status_code == 200 and restored.json()["file_size"] == 5
    versions = client.get(f"{asset['url']}/versions", headers=asset["h"]).json()
    assert versions[0]["version"] == 3 and versions[0]["restored_from_version"] == 1
    assert client.get(f"{asset['url']}/file", headers=asset["h"]).content == b"bueno"
    history = client.get(f"{asset['url']}/history", headers=asset["h"]).json()
    assert history[0]["action"] == "file_restored"
    # Restaurar la que ya es actual no tiene sentido.
    assert client.post(f"{asset['url']}/versions/{versions[0]['id']}/restore", headers=asset["h"]).status_code == 409


def test_restore_requires_lock_and_role(client, asset, login):
    upload(client, asset, b"a")
    upload(client, asset, b"b")
    v1 = client.get(f"{asset['url']}/versions", headers=asset["h"]).json()[1]
    artist = login("artist")
    client.post(f"/api/tenants/{asset['tid']}/members", json={"identifier": "artist", "role": "artist"}, headers=asset["h"])
    assert client.post(f"{asset['url']}/versions/{v1['id']}/restore", headers=artist).status_code == 403
    client.delete(f"{asset['url']}/lock", headers=asset["h"])
    assert client.post(f"{asset['url']}/versions/{v1['id']}/restore", headers=asset["h"]).status_code == 409


def test_versions_are_isolated_between_studios(client, asset, login):
    upload(client, asset, b"secreto")
    version = client.get(f"{asset['url']}/versions", headers=asset["h"]).json()[0]
    outsider = login("outsider")
    assert client.get(f"{asset['url']}/versions", headers=outsider).status_code == 403
    assert client.get(f"{asset['url']}/versions/{version['id']}/file", headers=outsider).status_code == 403
    assert client.get(f"{asset['url']}/versions/{version['id']}/preview", headers=outsider).status_code == 403


def test_deleting_asset_removes_every_version_file(client, asset):
    upload(client, asset, b"a")
    upload(client, asset, b"b")
    uploads = asset["tmp"] / "uploads"
    assert len([p for p in uploads.rglob("*") if p.is_file()]) == 2
    assert client.delete(asset["url"], headers=asset["h"]).status_code == 204
    assert [p for p in uploads.rglob("*") if p.is_file()] == []

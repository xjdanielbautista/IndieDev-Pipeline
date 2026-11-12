"""Pruebas de los ajustes finales: webhook robusto, limpieza de archivos y URL de base de datos."""

import hashlib
import hmac
import json

from app.database import normalize_database_url
from tests.test_pending_features import setup_project


def _signed_push(client, project_id, secret, commits):
    raw = json.dumps({"commits": commits}).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(
        f"/api/webhooks/github/{project_id}",
        content=raw,
        headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )


def _connect(client, tenant_id, project_id, headers):
    response = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/github",
        json={"github_repo": "owner/repo"},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["secret"]


def test_webhook_repeated_reference_and_redelivery(client, login):
    tenant_id, project_id, asset_id, headers = setup_project(client, login, "repeat-studio")
    secret = _connect(client, tenant_id, project_id, headers)
    commit = {
        "id": "a" * 40,
        "message": f"Arregla #{asset_id} (ver también #{asset_id})",
        "author": {"name": "Alex"},
        "url": "https://github.com/owner/repo/commit/aaa",
        "timestamp": "2026-10-20T08:15:00Z",
    }
    # El mismo commit dos veces en el push y la misma referencia dos veces en el mensaje.
    assert _signed_push(client, project_id, secret, [commit, commit]).status_code == 204
    # GitHub reintenta la entrega: no debe duplicar ni fallar.
    assert _signed_push(client, project_id, secret, [commit]).status_code == 204

    commits = client.get(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/commits", headers=headers
    ).json()
    assert len(commits) == 1


def test_webhook_tolerates_missing_fields(client, login):
    tenant_id, project_id, asset_id, headers = setup_project(client, login, "missing-studio")
    secret = _connect(client, tenant_id, project_id, headers)
    commits = [
        {"id": "b" * 40, "message": None},
        {"id": "c" * 40, "message": f"Sin autor #{asset_id}", "author": {"name": None}, "url": None},
        "no-es-un-objeto",
    ]
    assert _signed_push(client, project_id, secret, commits).status_code == 204

    saved = client.get(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/commits", headers=headers
    ).json()
    assert len(saved) == 1
    assert saved[0]["author_name"] == "Desconocido"


def test_delete_comment_checks_project(client, login):
    tenant_id, project_id, asset_id, headers = setup_project(client, login, "comment-scope")
    other = client.post(f"/api/tenants/{tenant_id}/projects", json={"name": "Otro"}, headers=headers).json()
    comment = client.post(
        f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}/comments",
        json={"body": "hola"},
        headers=headers,
    ).json()
    wrong = client.delete(
        f"/api/tenants/{tenant_id}/projects/{other['id']}/assets/{asset_id}/comments/{comment['id']}",
        headers=headers,
    )
    assert wrong.status_code == 404
    assert wrong.json()["detail"] != "Not Found"


def test_deleting_asset_removes_local_file(client, login, tmp_path, monkeypatch):
    monkeypatch.setenv("ASSET_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    tenant_id, project_id, asset_id, headers = setup_project(client, login, "cleanup-studio")
    base = f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}"
    assert client.patch(f"{base}/lock", json={}, headers=headers).status_code == 200
    uploaded = client.post(f"{base}/file", files={"file": ("engine.py", b"print(1)", "text/x-python")}, headers=headers)
    assert uploaded.status_code == 200
    stored = list((tmp_path / "uploads").rglob("*"))
    assert any(path.is_file() for path in stored)

    assert client.delete(base, headers=headers).status_code == 204
    assert not any(path.is_file() for path in (tmp_path / "uploads").rglob("*"))


def test_deleting_project_removes_its_files(client, login, tmp_path, monkeypatch):
    monkeypatch.setenv("ASSET_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("LOCAL_UPLOAD_DIR", str(tmp_path / "uploads"))
    tenant_id, project_id, asset_id, headers = setup_project(client, login, "cleanup-project")
    base = f"/api/tenants/{tenant_id}/projects/{project_id}/assets/{asset_id}"
    client.patch(f"{base}/lock", json={}, headers=headers)
    client.post(f"{base}/file", files={"file": ("engine.py", b"print(1)", "text/x-python")}, headers=headers)

    assert client.delete(f"/api/tenants/{tenant_id}/projects/{project_id}", headers=headers).status_code == 204
    assert not any(path.is_file() for path in (tmp_path / "uploads").rglob("*"))


def test_normalize_database_url():
    assert normalize_database_url("postgres://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("mysql+pymysql://u@h/db") == "mysql+pymysql://u@h/db"
    assert normalize_database_url("mysql://u@h/db") == "mysql+pymysql://u@h/db"
    assert normalize_database_url("sqlite:///./x.db") == "sqlite:///./x.db"

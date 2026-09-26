import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.database import get_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(main, "engine", test_engine)
    test_session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = test_session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    test_engine.dispose()


def test_tenant_scoping_and_kanban_task(client):
    first_tenant = client.post(
        "/api/tenants",
        json={"name": "Studio One", "slug": "studio-one", "owner_email": "one@example.com"},
    ).json()
    second_tenant = client.post(
        "/api/tenants",
        json={"name": "Studio Two", "slug": "studio-two", "owner_email": "two@example.com"},
    ).json()
    project = client.post(
        f"/api/tenants/{first_tenant['id']}/projects",
        json={"name": "My Game", "description": "Prototype"},
    ).json()

    task_response = client.post(
        f"/api/tenants/{first_tenant['id']}/projects/{project['id']}/tasks",
        json={"title": "Create player controller", "stage": "alpha", "area": "programming"},
    )

    assert task_response.status_code == 201
    assert task_response.json()["stage"] == "alpha"
    assert client.get(f"/api/tenants/{second_tenant['id']}/projects").json() == []
    assert client.get(
        f"/api/tenants/{second_tenant['id']}/projects/{project['id']}/tasks"
    ).status_code == 404


def test_asset_lock_requires_tenant_membership(client):
    tenant = client.post(
        "/api/tenants",
        json={"name": "Studio", "slug": "studio", "owner_email": "owner@example.com"},
    ).json()
    outsider = client.post(
        "/api/tenants",
        json={"name": "Other Studio", "slug": "other-studio", "owner_email": "other@example.com"},
    ).json()
    project = client.post(
        f"/api/tenants/{tenant['id']}/projects", json={"name": "Game"}
    ).json()
    asset = client.post(
        f"/api/tenants/{tenant['id']}/projects/{project['id']}/assets",
        json={"original_name": "model.fbx", "storage_key": "assets/model.fbx", "storage_provider": "s3"},
    ).json()

    locked = client.patch(
        f"/api/tenants/{tenant['id']}/assets/{asset['id']}/lock",
        json={"user_id": tenant["owner_user_id"]},
    )
    rejected = client.patch(
        f"/api/tenants/{tenant['id']}/assets/{asset['id']}/lock",
        json={"user_id": outsider["owner_user_id"]},
    )

    assert locked.status_code == 200
    assert locked.json()["locked_by_user_id"] == tenant["owner_user_id"]
    assert rejected.status_code == 403
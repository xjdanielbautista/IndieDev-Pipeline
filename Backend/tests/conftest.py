import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.database import get_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.security.SECRET_KEY", "x" * 40)
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


@pytest.fixture
def login(client):
    """Registra un usuario y devuelve sus headers con el token Bearer."""

    def _login(username: str) -> dict:
        client.post(
            "/api/auth/register",
            json={"username": username, "email": f"{username}@example.com", "password": "supersecreta1"},
        )
        token = client.post(
            "/api/auth/token", data={"username": username, "password": "supersecreta1"}
        ).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login

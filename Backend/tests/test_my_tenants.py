from tests.test_api import client  # noqa: F401  (reutiliza la fixture con BD temporal)


def auth_headers(client, username):
    client.post(
        "/api/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": "supersecreta1"},
    )
    token = client.post(
        "/api/auth/token", data={"username": username, "password": "supersecreta1"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_my_tenants_only_returns_memberships_with_role(client):  # noqa: F811
    owner = auth_headers(client, "owner")
    other = auth_headers(client, "other")
    client.post("/api/tenants", json={"name": "Studio A", "slug": "studio-a"}, headers=owner)
    client.post("/api/tenants", json={"name": "Studio B", "slug": "studio-b"}, headers=other)

    response = client.get("/api/tenants", headers=owner)

    assert response.status_code == 200
    assert [(t["name"], t["role"]) for t in response.json()] == [("Studio A", "owner")]
    assert client.get("/api/tenants").status_code == 401

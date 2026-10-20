def test_list_my_tenants_only_returns_memberships_with_role(client, login):
    owner = login("owner")
    other = login("other")
    client.post("/api/tenants", json={"name": "Studio A", "slug": "studio-a"}, headers=owner)
    client.post("/api/tenants", json={"name": "Studio B", "slug": "studio-b"}, headers=other)

    response = client.get("/api/tenants", headers=owner)

    assert response.status_code == 200
    assert [(t["name"], t["role"]) for t in response.json()] == [("Studio A", "owner")]
    assert client.get("/api/tenants").status_code == 401

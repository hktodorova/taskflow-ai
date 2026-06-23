import jwt
from app.config import get_settings


def test_login_returns_jwt(client):
    created = client.post(
        "/auth/register",
        json={"username": "jwt-user", "email": "jwt-user@example.com", "password": "secret123", "role": "member"},
    )
    assert created.status_code == 201

    login = client.post("/auth/login", json={"username": "jwt-user", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])

    assert payload["type"] == "access"
    assert payload["username"] == "jwt-user"
    assert payload["role"] == "member"
    assert "exp" in payload
    assert "." in token
    assert client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/me", headers={"Authorization": "Bearer legacy-api-token"}).status_code == 401


def test_duplicates_return_409(client, admin_headers):
    user_payload = {"username": "dupe", "email": "dupe@example.com", "password": "secret123", "role": "member"}
    assert client.post("/users", json=user_payload, headers=admin_headers).status_code == 201
    duplicate_user = client.post("/users", json=user_payload, headers=admin_headers)
    assert duplicate_user.status_code == 409

    assert client.post("/teams", json={"name": "Core Team"}, headers=admin_headers).status_code == 201
    duplicate_team = client.post("/teams", json={"name": "Core Team"}, headers=admin_headers)
    assert duplicate_team.status_code == 409

    user = client.post(
        "/users",
        json={"username": "member-one", "email": "member-one@example.com", "password": "secret123", "role": "member"},
        headers=admin_headers,
    ).json()
    team = client.post("/teams", json={"name": "Membership Team"}, headers=admin_headers).json()
    assert client.post(f"/teams/{team['id']}/members", json={"user_id": user["id"]}, headers=admin_headers).status_code == 201
    duplicate_member = client.post(f"/teams/{team['id']}/members", json={"user_id": user["id"]}, headers=admin_headers)
    assert duplicate_member.status_code == 409

    assert client.post("/projects", json={"name": "Core Project"}, headers=admin_headers).status_code == 201
    duplicate_project = client.post("/projects", json={"name": "Core Project"}, headers=admin_headers)
    assert duplicate_project.status_code == 409


def test_invalid_roles(client, admin_headers):
    bad_user = client.post(
        "/users",
        json={"username": "badrole", "email": "badrole@example.com", "password": "secret123", "role": "owner"},
        headers=admin_headers,
    )
    assert bad_user.status_code == 422

    user = client.post(
        "/users",
        json={"username": "valid-member", "email": "valid-member@example.com", "password": "secret123", "role": "member"},
        headers=admin_headers,
    ).json()
    team = client.post("/teams", json={"name": "Role Team"}, headers=admin_headers).json()
    bad_team_role = client.post(
        f"/teams/{team['id']}/members",
        json={"user_id": user["id"], "role": "superhero"},
        headers=admin_headers,
    )
    assert bad_team_role.status_code == 422


def test_task_pagination_limits_and_offsets(client, admin_headers):
    for i in range(5):
        res = client.post("/tasks", json={"title": f"Paginated task {i}"}, headers=admin_headers)
        assert res.status_code == 201

    first_page = client.get("/tasks", params={"limit": 2, "skip": 0}, headers=admin_headers)
    second_page = client.get("/tasks", params={"limit": 2, "skip": 2}, headers=admin_headers)
    assert first_page.status_code == 200
    assert second_page.status_code == 200
    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 2
    assert {task["id"] for task in first_page.json()}.isdisjoint({task["id"] for task in second_page.json()})

    assert client.get("/tasks", params={"limit": 0}, headers=admin_headers).status_code == 422
    assert client.get("/tasks", params={"limit": 1001}, headers=admin_headers).status_code == 422
    assert client.get("/tasks", params={"skip": -1}, headers=admin_headers).status_code == 422

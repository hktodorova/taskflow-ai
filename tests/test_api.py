from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import hash_password, new_token
from app.database import SessionLocal
from app.main import app
from app.models import User

client = TestClient(app)


def unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def _seed_user(username: str, email: str, password: str, role: str) -> None:
    """Insert a user directly into the DB, bypassing the public register endpoint."""
    db = SessionLocal()
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        api_token=new_token(),
        role=role,
    )
    db.add(user)
    db.commit()
    db.close()


def auth_headers(role: str = "admin") -> dict[str, str]:
    username = unique_name(role)
    password = "Test123!"
    email = f"{username}@example.com"

    _seed_user(username, email, password, role)

    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200, login.text

    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_main_workflow():
    headers = auth_headers("admin")

    member_name = unique_name("maria")
    user = client.post(
        "/users",
        headers=headers,
        json={
            "username": member_name,
            "email": f"{member_name}@example.com",
            "password": "Test123!",
            "full_name": "Maria Petrova",
            "role": "member",
        },
    )
    assert user.status_code == 201, user.text
    user_id = user.json()["id"]

    project = client.post(
        "/projects",
        headers=headers,
        json={
            "name": unique_name("SoftUni_Exam"),
            "description": "AI-assisted development",
        },
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    task = client.post(
        "/tasks",
        headers=headers,
        json={
            "title": unique_name("Build enterprise demo"),
            "priority": "critical",
            "project_id": project_id,
            "owner_id": user_id,
            "estimated_minutes": 120,
            "actual_minutes": 45,
            "tags": ["exam", "AI", "exam"],
        },
    )
    assert task.status_code == 201, task.text
    body = task.json()
    assert body["owner_id"] == user_id
    assert body["tags"] == ["ai", "exam"]

    comment = client.post(
        f"/tasks/{body['id']}/comments",
        headers=headers,
        json={"author": "tester", "body": "Looks good."},
    )
    assert comment.status_code == 201, comment.text
    assert len(comment.json()["comments"]) == 1

    activity = client.get("/activity", headers=headers)
    assert activity.status_code == 200, activity.text
    assert len(activity.json()) >= 2


def test_dependency_blocks_completion():
    headers = auth_headers("admin")

    first_response = client.post(
        "/tasks",
        headers=headers,
        json={"title": unique_name("Prepare DB"), "priority": "high"},
    )
    assert first_response.status_code == 201, first_response.text
    first = first_response.json()

    second_response = client.post(
        "/tasks",
        headers=headers,
        json={"title": unique_name("Build API"), "priority": "high"},
    )
    assert second_response.status_code == 201, second_response.text
    second = second_response.json()

    dep = client.post(
        f"/tasks/{second['id']}/dependencies",
        headers=headers,
        json={"depends_on_task_id": first["id"]},
    )
    assert dep.status_code == 201, dep.text

    blocked = client.post(f"/tasks/{second['id']}/complete", headers=headers)
    assert blocked.status_code == 409, blocked.text

    assert client.post(f"/tasks/{first['id']}/complete", headers=headers).status_code == 200
    assert client.post(f"/tasks/{second['id']}/complete", headers=headers).status_code == 200


def test_dashboard_and_export():
    headers = auth_headers("admin")

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    assert client.post(
        "/tasks",
        headers=headers,
        json={"title": unique_name("Overdue critical"), "priority": "critical", "due_date": yesterday},
    ).status_code == 201

    assert client.post(
        "/tasks",
        headers=headers,
        json={"title": unique_name("Upcoming"), "priority": "medium", "due_date": tomorrow},
    ).status_code == 201

    assert client.post(
        "/tasks",
        headers=headers,
        json={
            "title": unique_name("Blocked item"),
            "priority": "high",
            "status": "blocked",
            "blocked_reason": "Waiting for screenshots",
        },
    ).status_code == 201

    dashboard = client.get("/dashboard", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["analytics"]["overdue"] >= 1
    assert dashboard.json()["recommendations"]

    plan = client.get("/plan/today", headers=headers)
    assert plan.status_code == 200, plan.text
    assert set(plan.json()) == {"today", "upcoming", "backlog", "blocked"}

    export = client.get("/tasks/export.csv", headers=headers)
    assert export.status_code == 200, export.text
    assert "id,title,status,priority" in export.text


def test_filters_owner_and_validation():
    headers = auth_headers("admin")

    member_name = unique_name("ivan")
    user = client.post(
        "/users",
        headers=headers,
        json={
            "username": member_name,
            "email": f"{member_name}@example.com",
            "password": "Test123!",
            "role": "member",
        },
    )
    assert user.status_code == 201, user.text
    user_id = user.json()["id"]

    created = client.post(
        "/tasks",
        headers=headers,
        json={
            "title": unique_name("Owned Task"),
            "owner_id": user_id,
            "tags": ["demo"],
            "priority": "low",
        },
    )
    assert created.status_code == 201, created.text

    response = client.get(
        "/tasks",
        headers=headers,
        params={"owner_id": user_id, "tag": "demo", "priority": "low"},
    )
    assert response.status_code == 200, response.text
    assert any(task["owner_id"] == user_id for task in response.json())

    invalid = client.post(
        "/tasks",
        headers=headers,
        json={"title": unique_name("Blocked without reason"), "status": "blocked"},
    )
    assert invalid.status_code == 422, invalid.text


def test_auth_required():
    assert client.get("/tasks").status_code == 401

    headers = auth_headers("admin")
    assert client.get("/tasks", headers=headers).status_code == 200


def test_not_found_and_bad_request():
    headers = auth_headers("admin")

    response = client.post("/tasks/999999/complete", headers=headers)
    assert response.status_code == 404, response.text

    task_response = client.post(
        "/tasks",
        headers=headers,
        json={"title": unique_name("No self dependency")},
    )
    assert task_response.status_code == 201, task_response.text
    task = task_response.json()

    bad = client.post(
        f"/tasks/{task['id']}/dependencies",
        headers=headers,
        json={"depends_on_task_id": task["id"]},
    )
    assert bad.status_code == 400, bad.text


def test_task_crud():
    headers = auth_headers("admin")
    title = unique_name("CRUD Search Filter Demo")

    created = client.post(
        "/tasks",
        headers=headers,
        json={
            "title": title,
            "priority": "high",
            "tags": ["crud", "demo"],
            "description": "SoftUni searchable task",
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    read = client.get(f"/tasks/{task_id}", headers=headers)
    assert read.status_code == 200, read.text
    assert read.json()["title"] == title

    updated = client.patch(
        f"/tasks/{task_id}",
        headers=headers,
        json={"status": "active", "actual_minutes": 15},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "active"

    searched = client.get("/tasks/search", headers=headers, params={"q": "SoftUni"})
    assert searched.status_code == 200, searched.text
    assert any(task["id"] == task_id for task in searched.json())

    filtered = client.get(
        "/tasks",
        headers=headers,
        params={"priority": "high", "tag": "crud", "status": "active"},
    )
    assert filtered.status_code == 200, filtered.text
    assert any(task["id"] == task_id for task in filtered.json())

    completed = client.post(f"/tasks/{task_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"

    deleted = client.delete(f"/tasks/{task_id}", headers=headers)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 404

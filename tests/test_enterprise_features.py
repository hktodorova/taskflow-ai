from app.auth import hash_password, new_token
from app.database import SessionLocal
from app.models import User


def _seed_user(username: str, email: str, password: str, role: str) -> None:
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


def test_login_and_me(client):
    created = client.post("/auth/register", json={"username":"maria", "email":"maria@example.com", "password":"secret123", "role":"member"})
    assert created.status_code == 201
    login = client.post("/auth/login", json={"username":"maria", "password":"secret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "maria"


def test_viewer_cannot_create(client):
    _seed_user("viewer", "viewer@example.com", "secret123", "viewer")
    token = client.post("/auth/login", json={"username":"viewer", "password":"secret123"}).json()["access_token"]
    res = client.post("/projects", json={"name":"Secret"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_teams_and_projects(client, admin_headers):
    user = client.post("/users", json={"username":"dev", "email":"dev@example.com", "password":"secret123", "role":"member"}, headers=admin_headers).json()
    team = client.post("/teams", json={"name":"AI Team"}, headers=admin_headers).json()
    member = client.post(f"/teams/{team['id']}/members", json={"user_id": user["id"], "role":"developer"}, headers=admin_headers)
    assert member.status_code == 201
    project = client.post("/projects", json={"name":"Exam Project", "team_id": team["id"]}, headers=admin_headers)
    assert project.status_code == 201
    assert project.json()["team_id"] == team["id"]


def test_task_flow(client, admin_headers):
    user = client.post("/users", json={"username":"owner", "email":"owner@example.com", "password":"secret123", "role":"member"}, headers=admin_headers).json()
    project = client.post("/projects", json={"name":"Core"}, headers=admin_headers).json()
    task = client.post("/tasks", json={"title":"Build analytics dashboard", "priority":"critical", "project_id":project["id"], "owner_id":user["id"], "tags":["analytics", "api"]}, headers=admin_headers)
    assert task.status_code == 201
    tid = task.json()["id"]
    assert client.get("/tasks/search?q=analytics", headers=admin_headers).json()[0]["id"] == tid
    assert client.get("/tasks?priority=critical&tag=api", headers=admin_headers).json()[0]["title"] == "Build analytics dashboard"
    completed = client.post(f"/tasks/{tid}/complete", headers=admin_headers)
    assert completed.json()["status"] == "completed"
    assert client.get("/analytics", headers=admin_headers).json()["completion_rate"] == 100.0
    assert "recommendations" in client.get("/dashboard", headers=admin_headers).json()


def test_notifications_and_jobs(client, admin_headers):
    client.post("/tasks", json={"title":"Fix production bug", "priority":"critical", "tags":["ai"]}, headers=admin_headers)
    ai = client.get("/ai/recommendations", headers=admin_headers)
    assert ai.status_code == 200
    assert ai.json()[0]["confidence"] > 0.7
    email = client.post("/notifications/email", json={"recipient":"student@example.com", "subject":"Reminder", "body":"Finish the report"}, headers=admin_headers)
    assert email.status_code == 201
    job = client.post("/jobs", json={"job_type":"send_emails"}, headers=admin_headers)
    assert job.status_code == 201
    run = client.post("/jobs/run", headers=admin_headers)
    assert run.json()["processed"] == 1
    outbox = client.get("/notifications/email", headers=admin_headers).json()
    assert outbox[0]["status"] == "sent"

import os, tempfile
import pytest
from fastapi.testclient import TestClient

# Each test session uses an isolated SQLite database.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), "taskflow_test.db")
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-32-bytes"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from app.auth import hash_password, new_token
from app.database import Base, engine, SessionLocal
from app.main import app, _login_attempts
from app.models import User

@pytest.fixture(autouse=True)
def reset_db():
    _login_attempts.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def admin_headers(client):
    db = SessionLocal()
    user = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password("secret123"),
        api_token=new_token(),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.close()
    res = client.post("/auth/login", json={"username": "admin", "password": "secret123"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

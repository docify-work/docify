from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def auth_headers() -> dict[str, str]:
    client.post("/auth/signup", json={"email": "a@example.com", "password": "pw-123456"})
    token = client.post("/auth/login", json={"email": "a@example.com", "password": "pw-123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_tasks():
    h = auth_headers()
    assert client.post("/tasks", json={"title": "write docs", "priority": 1}, headers=h).status_code == 201
    titles = [t["title"] for t in client.get("/tasks", headers=h).json()]
    assert "write docs" in titles


def test_rejects_bad_priority():
    h = auth_headers()
    assert client.post("/tasks", json={"title": "x", "priority": 9}, headers=h).status_code == 422

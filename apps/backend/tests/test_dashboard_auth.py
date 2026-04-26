from __future__ import annotations

from fastapi.testclient import TestClient

from zen_backend.main import app


def test_dashboard_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/dashboard/today")
    assert response.status_code == 401


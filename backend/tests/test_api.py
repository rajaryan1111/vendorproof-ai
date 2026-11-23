from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_and_errors(monkeypatch):
    monkeypatch.setenv("VP_CORS_ORIGINS", '["http://example.test"]')
    client = TestClient(create_app(Settings()))
    response = client.get("/api/v1/health", headers={"Origin": "http://example.test"})
    assert response.json() == {"status": "ok"}
    assert response.headers["access-control-allow-origin"] == "http://example.test"
    assert response.headers["x-request-id"]
    denied = client.get("/api/v1/health", headers={"Origin": "http://other.test"})
    assert "access-control-allow-origin" not in denied.headers
    assert client.get("/missing").json() == {"error": {"code": "http_404"}}


def test_cookie_and_cors_defaults():
    import pytest
    from pydantic import ValidationError

    assert Settings(_env_file=None, cookie_secure=True).cookie_secure
    with pytest.raises(ValidationError):
        Settings(cors_origins=["*"])

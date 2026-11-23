import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import engine_for
from app.main import create_app
from app.provision import provision


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    import os

    url = os.environ.get("VP_TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "Set VP_TEST_DATABASE_URL to a migrated disposable PostgreSQL database"
        )
    monkeypatch.setenv("VP_DATABASE_URL", url)
    settings = Settings(cookie_secure=False, storage_root=tmp_path)
    app = create_app(settings)
    org = uuid4().hex
    result = {}
    with engine_for(settings).begin() as conn:
        for role in ["admin", "operator", "reviewer", "auditor", "outside"]:
            name = org if role != "outside" else uuid4().hex
            email = uuid4().hex + "@example.invalid"
            secret = secrets.token_urlsafe(24)
            provision(conn, name, email, secret, "admin" if role == "outside" else role)
            result[role] = (email, name, secret)
    clients = {}
    for role, (email, workspace, password) in result.items():
        client = TestClient(
            app, client=(uuid4().hex, 1234), headers={"X-VP-Request": "1"}
        )
        body = {"email": email, "workspace": workspace, "password": password}
        assert (
            client.post(
                "/api/v1/login", json={**body, "password": "invalid"}
            ).status_code
            == 401
        )
        assert client.post("/api/v1/login", json=body).status_code == 200
        clients[role] = client
    yield clients
    for client in clients.values():
        client.close()
    app.state.engine.dispose()

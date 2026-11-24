from fastapi.testclient import TestClient
from sqlalchemy import text

from app.platform_check import app


def test_platform_check_cannot_accept_workspace_data():
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json()["status"] == "validation_only"
        for method, path in [
            ("GET", "/api/v1/health/db"),
            ("GET", "/api/v1/account"),
            ("POST", "/api/v1/login"),
            ("POST", "/api/v1/suppliers/fixture/documents"),
        ]:
            response = client.request(method, path)
            assert response.status_code == 503
            assert response.headers["cache-control"] == "no-store"


def test_member_changes_are_scoped_audited_and_revoke_sessions(accounts):
    admin, reviewer, outside = (accounts[k] for k in ("admin", "reviewer", "outside"))
    url = "/api/v1/organization/members"
    rows = admin.get(url).json()["members"]
    assert len(rows) == 4 and reviewer.get(url).status_code == 403
    member = next(m for m in rows if m["role"] == "reviewer")
    target = url + "/" + member["id"]
    payload = {
        "role": "auditor",
        "active": False,
        "previous_role": "reviewer",
        "previous_active": True,
    }
    assert outside.patch(target, json=payload).status_code == 404
    assert reviewer.patch(target, json=payload).status_code == 403
    own = next(m for m in rows if m["own"])
    assert admin.patch(url + "/" + own["id"], json=payload).status_code == 403
    assert admin.patch(target, json=payload).is_success
    assert admin.patch(target, json=payload).is_success
    assert admin.patch(target, json={**payload, "active": True}).status_code == 409
    assert reviewer.get("/api/v1/account").status_code == 401
    assert admin.patch(
        target,
        json={
            **payload,
            "previous_role": "auditor",
            "previous_active": False,
            "active": True,
        },
    ).is_success
    assert reviewer.get("/api/v1/account").status_code == 401
    with admin.app.state.engine.connect() as conn:
        events = conn.execute(
            text(
                "SELECT old_role,new_role,was_active,is_active FROM member_access_events WHERE member_id=:id ORDER BY id"
            ),
            {"id": member["id"]},
        ).all()
        assert events == [
            ("reviewer", "auditor", True, False),
            ("auditor", "auditor", False, True),
        ]

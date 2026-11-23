import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.verification import api


def test_history_isolation_and_role_gates(accounts, monkeypatch):
    admin = accounts["admin"]
    operator = accounts["operator"]
    auditor = accounts["auditor"]
    reviewer = accounts["reviewer"]
    outside = accounts["outside"]
    sid = admin.post("/api/v1/suppliers", json={"name": "Synthetic test"}).json()["id"]
    path = f"/api/v1/suppliers/{sid}/verification"
    config = {"rules": [{"category": "tax", "when_jurisdiction": "XY"}]}
    assert admin.post(path + "/runs").status_code == 409
    for client in [operator, reviewer, auditor]:
        assert client.put(path + "/policy?previous=0", json=config).status_code == 403
    assert outside.put(path + "/policy?previous=0", json=config).status_code == 404
    assert admin.put(path + "/policy?previous=0", json=config).json()["version"] == 1
    assert admin.put(path + "/policy?previous=0", json=config).status_code == 409
    assert auditor.post(path + "/runs").status_code == 403
    rid = operator.post(path + "/runs").json()["id"]
    assert reviewer.post(path + "/runs").json()["id"] == rid
    route = path + "/runs/" + rid
    result = admin.get(route).json()
    assert result["checklist"][0]["outcome"] == "unknown_condition"
    fid = result["findings"][0]["id"]
    action = path + "/findings/" + fid + "/review"
    data = {
        "status": "clarification_requested",
        "reason": "Confirm jurisdiction",
        "previous": 0,
    }
    assert outside.get(route).status_code == 404
    assert operator.post(action, json=data).status_code == 403
    assert auditor.post(action, json=data).status_code == 403
    assert outside.post(action, json=data).status_code == 404
    assert reviewer.post(action, json={**data, "reason": "  "}).status_code == 422
    first = reviewer.post(action, json=data).json()["seq"]
    assert reviewer.post(action, json=data).status_code == 409
    assert (
        reviewer.post(
            action,
            json={
                **data,
                "previous": first,
                "status": "resolved",
                "reason": "Supporting certificate inspected",
            },
        ).status_code
        == 200
    )
    assert "reason" not in auditor.get(route).json()["findings"][0]["history"][0]
    with pytest.raises(DBAPIError), admin.app.state.engine.begin() as conn:
        conn.execute(
            text("UPDATE verification_reviews SET reason='change' WHERE seq=:seq"),
            {"seq": first},
        )
    assert (
        admin.put(
            path + "/policy?previous=1", json={**config, "jurisdiction": "XY"}
        ).json()["version"]
        == 2
    )
    new = admin.post(path + "/runs").json()["id"]
    assert rid != new
    assert admin.get(route).json()["policy_version"] == 1
    assert (
        admin.get(path + "/runs/" + new).json()["checklist"][0]["outcome"]
        == "missing_document"
    )
    assert reviewer.post(action, json=data).status_code == 409
    monkeypatch.setattr(api, "VERSION", "test/2")
    assert admin.post(path + "/runs").json()["id"] != new

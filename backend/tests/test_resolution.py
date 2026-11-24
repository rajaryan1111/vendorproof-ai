from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.intelligence.worker import run_one
from app.resolution.domain import guidance
from evaluation.v1.fixtures import make_pdf

ROOT = "/api/v1/exceptions"


def seed(admin):
    sid = admin.post("/api/v1/suppliers", json={"name": "Synthetic resolution"}).json()[
        "id"
    ]
    base = f"/api/v1/suppliers/{sid}"
    policy = base + "/verification/policy?previous=0"
    assert (
        admin.put(policy, json={"rules": [{"category": "agreement"}]}).status_code
        == 200
    )
    rid = admin.post(base + "/verification/runs").json()["id"]
    rows = admin.get(base + "/verification/runs/" + rid).json()["findings"]
    fid = next(f["id"] for f in rows if f["rule"] == "requirement")
    return base, ROOT + "/" + fid


def actor(client):
    return client.get("/api/v1/account").json()["actor"]


def test_assignment_drafts_lifecycle(accounts):
    admin, reviewer, outside = [accounts[r] for r in ("admin", "reviewer", "outside")]
    base, path = seed(admin)
    review_id = actor(reviewer)
    assignment = {
        "previous": 0,
        "assignee": review_id,
        "reason": "Inspect missing supplier agreement.",
    }
    for role in ("operator", "auditor", "reviewer"):
        assert (
            accounts[role].post(path + "/assignment", json=assignment).status_code
            == 403
        )
    assert (
        outside.get(path).status_code == 404 and outside.get(ROOT).json()["items"] == []
    )
    assert outside.post(path + "/assignment", json=assignment).status_code == 404
    assert (
        admin.post(
            path + "/assignment", json={**assignment, "assignee": actor(outside)}
        ).status_code
        == 422
    )
    assert (
        admin.post(
            path + "/assignment",
            json={**assignment, "assignee": actor(accounts["auditor"])},
        ).status_code
        == 422
    )
    with ThreadPoolExecutor(2) as pool:
        responses = list(
            pool.map(
                lambda _: admin.post(path + "/assignment", json=assignment).status_code,
                range(2),
            )
        )
    assert sorted(responses) == [200, 409]
    detail = reviewer.get(path).json()
    assert detail["owner"] and detail["status"] == "assigned"
    assert (
        detail["guidance"]["action"]
        == "Please provide the required agreement document."
    )
    for query, expected in [
        ("owner=mine&q=resolution&status=assigned&severity=medium&sort=age", 1),
        ("age=1", 0),
        ("page=2", 0),
        ("owner=unassigned&status=assigned", 0),
    ]:
        assert len(reviewer.get(ROOT + "?" + query).json()["items"]) == expected
    assert reviewer.get(ROOT + "?owner=" + review_id).json()["counts"] == {
        "mine": 1,
        "unassigned": 0,
        "total": 1,
    }
    guide = detail["guidance"]
    draft = {"previous": 0, "subject": guide["subject"], "message": guide["message"]}
    for role in ("operator", "auditor"):
        assert accounts[role].post(path + "/drafts", json=draft).status_code == 403
    assert outside.post(path + "/drafts", json=draft).status_code == 404
    assert (
        reviewer.post(
            path + "/drafts",
            json={
                **draft,
                "message": draft["message"] + "\nInternal note with raw details",
            },
        ).status_code
        == 422
    )
    assert reviewer.post(path + "/drafts", json=draft).json() == {"revision": 1}
    assert reviewer.post(path + "/drafts", json=draft).json() == {"revision": 1}
    edited = {**draft, "message": draft["message"] + "\n" + guide["sentences"][-1]}
    assert reviewer.post(path + "/drafts", json=edited).status_code == 409
    assert reviewer.post(path + "/drafts", json={**edited, "previous": 1}).json() == {
        "revision": 2
    }
    assert accounts["auditor"].get(path).json()["drafts"] == []
    seq = detail["revision"]
    seq = admin.post(
        path + "/assignment",
        json={**assignment, "previous": seq, "assignee": actor(admin)},
    ).json()["seq"]
    assert reviewer.get(path).json()["drafts"] == []
    assert (
        reviewer.post(
            path + "/decision",
            json={"previous": seq, "status": "resolved", "reason": "test"},
        ).status_code
        == 403
    )
    legacy = base + "/verification/findings/" + path.split("/")[-1] + "/review"
    assert (
        admin.post(
            legacy, json={"previous": seq, "status": "resolved", "reason": "Bypass"}
        ).status_code
        == 409
    )
    for status in [
        "awaiting_supplier_response",
        "awaiting_internal_review",
        "resolved",
        "reopened",
    ]:
        body = {"previous": seq, "status": status, "reason": "Synthetic human decision"}
        if status == "awaiting_internal_review":
            assert (
                admin.post(
                    path + "/decision", json={**body, "status": "resolved"}
                ).status_code
                == 409
            )
        assert (
            admin.post(path + "/decision", json={**body, "reason": " "}).status_code
            == 422
        )
        seq = admin.post(path + "/decision", json=body).json()["seq"]
        assert admin.post(path + "/decision", json=body).status_code == 409
    detail = admin.get(path).json()
    assert len(detail["history"]) == 6 and detail["status"] == "reopened"
    assert all(
        h["actor"] and h["from_state"] and h["created_at"] for h in detail["history"]
    )
    assert "reason" not in accounts["auditor"].get(path).json()["history"][0]
    engine = admin.app.state.engine
    for table, condition in [
        ("exception_drafts", "finding_id"),
        ("verification_runs", "id"),
        ("verification_findings", "id"),
    ]:
        with (
            pytest.raises(DBAPIError, match="immutable verification history"),
            engine.begin() as conn,
        ):
            conn.execute(
                text(f"DELETE FROM {table} WHERE {condition}=:id"),
                {
                    "id": detail["run_id"]
                    if table == "verification_runs"
                    else detail["id"]
                },
            )
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE memberships SET active=false WHERE user_id=:id"),
            {"id": review_id},
        )
    assert reviewer.get(path).status_code == 401
    assert (
        admin.post(
            path + "/assignment", json={**assignment, "previous": seq}
        ).status_code
        == 422
    )


def test_correction_retries_and_failed_evidence(accounts):
    admin = accounts["admin"]
    base, path = seed(admin)
    fid = path.rsplit("/", 1)[1]
    docs = base + "/documents"
    headers = {"Content-Type": "application/pdf", "X-Filename": "synthetic.pdf"}
    data = make_pdf({"pages": ["Supplier agreement"], "media": ["native"]})
    key = str(uuid4())
    url = docs + f"?finding_id={fid}&request_id={key}"
    assert admin.post(url, headers=headers, content=b"invalid").status_code == 415
    assert (
        accounts["reviewer"].post(url, headers=headers, content=data).status_code == 403
    )
    assert (
        accounts["outside"].post(url, headers=headers, content=data).status_code == 404
    )
    assert (
        admin.post(
            url + "&replaces=" + str(uuid4()), headers=headers, content=data
        ).status_code
        == 422
    )
    doc = accounts["operator"].post(url, headers=headers, content=data).json()["id"]
    assert admin.post(url, headers=headers, content=data).json()["id"] == doc
    assert (
        admin.post(
            url,
            headers=headers,
            content=make_pdf({"pages": ["Other"], "media": ["native"]}),
        ).status_code
        == 409
    )
    job = admin.get(path).json()["corrections"][0]
    assert len(admin.get(docs + "/" + doc + "/processing").json()) == 1
    early = {"previous": 0, "reason": "Review evidence", "status": "resolved"}
    assert admin.post(path + "/compare", json={"previous": 0}).status_code == 409
    assert admin.post(path + "/decision", json=early).status_code == 409
    # Deliberately corrupt only the synthetic private test fixture to exercise digest failure.
    tenant = admin.get("/api/v1/account").json()["tenant"]
    (admin.app.state.settings.storage_root / tenant / doc).write_bytes(b"fixture")
    assert run_one(
        admin.app.state.engine, admin.app.state.settings, UUID(job["attempt"])
    )
    event = admin.post(path + "/compare", json={"previous": 0}).json()
    assert admin.post(path + "/compare", json={"previous": 0}).json() == event
    after = admin.get(path).json()
    assert (
        after["status"] == "open"
        and after["corrections"][0]["error_code"] == "version_mismatch"
    )
    assert (
        admin.post(
            path + "/decision",
            json={
                **early,
                "previous": event["seq"],
                "reviewed_run": after["comparison"]["compared_run"],
            },
        ).status_code
        == 409
    )
    replacement = admin.post(
        docs + f"?finding_id={fid}&replaces={doc}&request_id={uuid4()}",
        headers=headers,
        content=data,
    ).json()["id"]
    job = admin.get(path).json()["corrections"][0]
    assert (
        job["document_id"] == replacement
        and admin.get(docs + "/" + doc).status_code == 404
    )
    assert run_one(
        admin.app.state.engine, admin.app.state.settings, UUID(job["attempt"])
    )
    result = admin.post(path + "/compare", json={"previous": event["seq"]}).json()
    after = admin.get(path).json()
    assert (
        after["status"] == "open"
        and after["comparison"]["current"][0]["outcome"] == "received"
    )
    assert (
        admin.post(
            path + "/decision", json={**early, "previous": result["seq"]}
        ).status_code
        == 409
    )
    assert (
        admin.post(
            path + "/decision",
            json={
                **early,
                "previous": result["seq"],
                "reviewed_run": after["comparison"]["compared_run"],
            },
        ).json()["status"]
        == "resolved"
    )


@pytest.mark.parametrize(
    ("rule", "outcome", "word"),
    [
        ("expiry_date", "expired", "validity period"),
        ("bank_holder", "conflict", "account holder"),
        ("name", "conflict", "registration"),
        ("page_quality", "insufficient", "clearer"),
    ],
)
def test_guidance_privacy(rule, outcome, word):
    guide = guidance(rule, outcome, "Internal test context")
    assert word in guide["action"] and "Internal" not in guide["message"]


def test_queue_page_boundaries_and_archive(accounts):
    admin = accounts["admin"]
    base, path = seed(admin)
    original = admin.get(path).json()
    with admin.app.state.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO verification_findings(organization_id,supplier_id,run_id,rule,outcome,severity,explanation,quality,requires_review,evidence,created_at)
            SELECT organization_id,supplier_id,run_id,rule,outcome,severity,explanation,quality,requires_review,evidence,now()-interval '10 days'
            FROM verification_findings CROSS JOIN generate_series(1,21) WHERE id=:fid"""),
            {"fid": original["id"]},
        )
    for sort in ("severity", "age", "supplier", "status"):
        first = admin.get(ROOT, params={"sort": sort, "age": 5}).json()
        second = admin.get(ROOT, params={"sort": sort, "age": 5, "page": 2}).json()
        assert (
            first["counts"]["total"] == 21
            and len(first["items"]) == 20
            and len(second["items"]) == 1
        )
        assert second["items"][0]["id"] not in {i["id"] for i in first["items"]}
    assert admin.delete(base).is_success
    assert (
        admin.get(path).json()["archived"] and not admin.get(path).json()["transitions"]
    )
    assert (
        admin.post(
            path + "/decision",
            json={"previous": 0, "reason": "Synthetic", "status": "dismissed"},
        ).status_code
        == 409
    )

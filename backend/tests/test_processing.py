from uuid import UUID

from app.intelligence.worker import run_one
from evaluation.v1.fixtures import make_pdf


def test_attempts_and_permissions(accounts):
    admin = accounts["admin"]
    sid = admin.post("/api/v1/suppliers", json={"name": "Synthetic"}).json()["id"]
    docs = f"/api/v1/suppliers/{sid}/documents"
    pdf = make_pdf(
        {"pages": ["Bank verification letter\nIFSC: SYNTHETIC"], "media": ["native"]}
    )
    key = admin.post(
        docs,
        headers={"Content-Type": "application/pdf", "X-Filename": "example.pdf"},
        content=pdf,
    ).json()["id"]
    path = f"{docs}/{key}/processing"
    job = admin.get(path).json()[0]
    assert job["state"] == "queued"
    assert admin.post(path).json()["id"] == job["id"]
    assert accounts["auditor"].post(path).status_code == 403
    assert accounts["outside"].get(path).status_code == 404
    engine = admin.app.state.engine
    settings = admin.app.state.settings
    assert run_one(engine, settings, UUID(job["id"]))
    assert not run_one(engine, settings, UUID(job["id"]))
    assert admin.get(path).json()[0]["state"] == "needs_review"
    result = path + "/" + job["id"]
    assert admin.get(result).json()["document_id"] == key
    assert accounts["reviewer"].get(result).status_code == 403
    assert accounts["outside"].get(result).status_code == 404
    summary = accounts["reviewer"].get(result + "?summary=true")
    assert summary.status_code == 200 and "SYNTHETIC" not in summary.text
    assert accounts["outside"].get(result + "?summary=true").status_code == 404
    retry = path + "?after=" + job["id"]
    second = admin.post(retry).json()["id"]
    assert second != job["id"] and admin.post(retry).json()["id"] == second
    tenant = admin.get("/api/v1/account").json()["tenant"]
    (settings.storage_root / tenant / key).write_bytes(b"corrupt")
    assert run_one(engine, settings, UUID(second))
    attempts = admin.get(path).json()
    assert [r["state"] for r in attempts] == ["failed", "needs_review"]
    assert attempts[0]["error_code"] == "version_mismatch"
    assert admin.get(result).json()["document_id"] == key

    third = admin.post(path + "?after=" + second).json()["id"]
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE processing_attempts SET state='processing',started_at=now()-interval '5 minutes' WHERE id=:id"
            ),
            {"id": third},
        )
    assert not run_one(engine, settings, UUID(third))
    assert admin.get(path).json()[0]["error_code"] == "worker_interrupted"

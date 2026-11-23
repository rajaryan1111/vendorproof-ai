from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from ..auth import identity, writer
from ..db import db, query
from ..suppliers import lookup
from .schema import ENGINE, SCHEMA

router = APIRouter(prefix="/api/v1/suppliers/{sid}/documents/{key}/processing")


def enqueue(conn, tenant, sid, key, attempt=1):
    return query(
        conn,
        """INSERT INTO processing_attempts(organization_id,supplier_id,document_id,attempt,implementation,schema_version)
    VALUES(:tenant,:sid,:key,:attempt,:engine,:schema) RETURNING id,state,attempt""",
        tenant=tenant,
        sid=sid,
        key=key,
        attempt=attempt,
        engine=ENGINE,
        schema=SCHEMA,
    ).one()


def require_doc(conn, tenant, sid, key, lock=False):
    if not query(
        conn,
        "SELECT id FROM documents WHERE organization_id=:tenant AND supplier_id=:sid AND id=:key AND NOT archived"
        + (" FOR UPDATE" if lock else ""),
        tenant=tenant,
        sid=sid,
        key=key,
    ).first():
        raise HTTPException(404)


@router.post("")
def process(
    sid: UUID,
    key: UUID,
    after: UUID | None = None,
    user=Depends(writer, scope="function"),
    conn=Depends(db, scope="function"),
):
    if lookup(conn, user, sid, True).archived:
        raise HTTPException(409)
    require_doc(conn, user.tenant, sid, key, True)
    last = query(
        conn,
        "SELECT id,state,attempt FROM processing_attempts WHERE organization_id=:tenant AND document_id=:key ORDER BY attempt DESC LIMIT 1",
        tenant=user.tenant,
        key=key,
    ).first()
    if last and (after != last.id or last.state in ("queued", "processing")):
        return dict(last)
    if last and last.attempt >= 10:
        raise HTTPException(409)
    return dict(enqueue(conn, user.tenant, sid, key, last.attempt + 1 if last else 1))


@router.get("")
def history(
    sid: UUID,
    key: UUID,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    require_doc(conn, user.tenant, sid, key)
    cols = """id,state,attempt,implementation,schema_version,created_at,started_at,finished_at,error_code,
    report->'classification'->>'category' AS category,
    jsonb_array_length(report->'pages') AS pages,
    (SELECT count(*) FROM jsonb_array_elements(report->'candidates') f WHERE f->>'status'='candidate') AS candidate_count"""
    rows = query(
        conn,
        "SELECT "
        + cols
        + " FROM processing_attempts WHERE organization_id=:tenant AND document_id=:key ORDER BY attempt DESC",
        tenant=user.tenant,
        key=key,
    )
    return [dict(r) for r in rows]


@router.get("/{attempt}")
def result(
    sid: UUID,
    key: UUID,
    attempt: UUID,
    summary: bool = False,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    require_doc(conn, user.tenant, sid, key)
    if user.role != "admin" and not (summary and user.role == "reviewer"):
        raise HTTPException(403)
    row = query(
        conn,
        "SELECT report FROM processing_attempts WHERE organization_id=:tenant AND document_id=:key AND id=:attempt",
        tenant=user.tenant,
        key=key,
        attempt=attempt,
    ).first()
    if not row:
        raise HTTPException(404)
    if not row.report:
        raise HTTPException(409)
    if summary:
        # Build an allowlisted view. Free text and candidate values inherit PDF access.
        report = row.report
        return {
            "category": report["classification"]["category"],
            "fields": [
                {
                    "key": c["key"],
                    "status": c["status"],
                    "pages": sorted(
                        {
                            r["page"]
                            for r in ([c["source"]] if c["source"] else [])
                            + c["alternatives"]
                        }
                    ),
                }
                for c in report["candidates"]
            ],
            "pages": [
                {"number": p["number"], "warning": p["warning"]}
                for p in report["pages"]
            ],
        }
    return row.report

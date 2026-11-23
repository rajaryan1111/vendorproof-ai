from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .auth import identity, writer
from .db import db, query

router = APIRouter(prefix="/api/v1")


class Supplier(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    contact: str = Field(default="", max_length=240)


def lookup(conn, user, sid, lock=False):
    row = query(
        conn,
        "SELECT * FROM suppliers WHERE organization_id=:tenant AND id=:sid"
        + (" FOR UPDATE" if lock else ""),
        tenant=user.tenant,
        sid=sid,
    ).first()
    if not row:
        raise HTTPException(404)
    return row


def event(conn, user, sid, action):
    query(
        conn,
        "INSERT INTO activity(organization_id,supplier_id,actor,action) VALUES(:tenant,:sid,:actor,:action)",
        tenant=user.tenant,
        sid=sid,
        actor=user.actor,
        action=action,
    )


@router.get("/suppliers")
def directory(
    q: str = Query("", max_length=160),
    archived: bool = False,
    page: int = Query(1, ge=1, le=1000000),
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    return [
        dict(r)
        for r in query(
            conn,
            "SELECT * FROM suppliers WHERE organization_id=:tenant AND archived=:archived AND strpos(lower(name),lower(:q))>0 ORDER BY name,id LIMIT 20 OFFSET :skip",
            tenant=user.tenant,
            q=q,
            archived=archived,
            skip=(page - 1) * 20,
        )
    ]


@router.post("/suppliers", status_code=201)
def create(
    body: Supplier,
    user=Depends(writer, scope="function"),
    conn=Depends(db, scope="function"),
):
    row = query(
        conn,
        "INSERT INTO suppliers(organization_id,name,contact) VALUES(:tenant,:name,:contact) RETURNING *",
        tenant=user.tenant,
        **body.model_dump(),
    ).one()
    event(conn, user, row.id, "Created supplier")
    return dict(row)


@router.get("/suppliers/{sid}")
def detail(
    sid: UUID,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    return dict(lookup(conn, user, sid))


@router.patch("/suppliers/{sid}")
def update(
    sid: UUID,
    body: Supplier,
    user=Depends(writer, scope="function"),
    conn=Depends(db, scope="function"),
):
    if lookup(conn, user, sid, True).archived:
        raise HTTPException(409)
    row = query(
        conn,
        "UPDATE suppliers SET name=:name,contact=:contact,updated_at=now() WHERE id=:sid AND organization_id=:tenant RETURNING *",
        sid=sid,
        tenant=user.tenant,
        **body.model_dump(),
    ).one()
    event(conn, user, sid, "Updated supplier")
    return dict(row)


@router.delete("/suppliers/{sid}")
def archive(
    sid: UUID,
    user=Depends(writer, scope="function"),
    conn=Depends(db, scope="function"),
):
    if user.role != "admin":
        raise HTTPException(403)
    if not lookup(conn, user, sid, True).archived:
        query(
            conn,
            "UPDATE suppliers SET archived=true,updated_at=now() WHERE id=:sid AND organization_id=:tenant",
            sid=sid,
            tenant=user.tenant,
        )
        event(conn, user, sid, "Archived supplier")
    return {"archived": True}


@router.get("/dashboard")
def dashboard(
    user=Depends(identity, scope="function"), conn=Depends(db, scope="function")
):
    counts = query(
        conn,
        """SELECT count(*) total,count(*) FILTER(WHERE NOT archived) active,count(*) FILTER(WHERE archived) archived,
    (SELECT count(*) FROM documents WHERE organization_id=:tenant AND NOT archived) documents, (SELECT count(*) FROM documents d WHERE d.organization_id=:tenant AND NOT d.archived AND (SELECT state FROM processing_attempts j WHERE j.document_id=d.id ORDER BY attempt DESC LIMIT 1)='needs_review') needs_review FROM suppliers WHERE organization_id=:tenant""",
        tenant=user.tenant,
    ).one()
    recent = query(
        conn,
        "SELECT s.name,a.action,a.created_at FROM activity a JOIN suppliers s ON s.id=a.supplier_id AND s.organization_id=a.organization_id WHERE a.organization_id=:tenant ORDER BY a.id DESC LIMIT 10",
        tenant=user.tenant,
    )
    pending = (
        query(
            conn,
            """SELECT count(*) n FROM (SELECT DISTINCT ON (supplier_id) id FROM verification_runs WHERE organization_id=:tenant ORDER BY supplier_id,created_at DESC,id DESC) latest
    JOIN verification_findings f ON f.run_id=latest.id JOIN suppliers s ON s.id=f.supplier_id AND NOT s.archived
    WHERE f.organization_id=:tenant AND f.requires_review AND COALESCE((SELECT status FROM verification_reviews v WHERE v.finding_id=f.id ORDER BY seq DESC LIMIT 1),'open') NOT IN ('dismissed','resolved')""",
            tenant=user.tenant,
        )
        .one()
        .n
    )
    return {
        "verification_pending": pending,
        **counts,
        "recent": [dict(r) for r in recent],
    }

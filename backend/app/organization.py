from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import identity
from .db import db, query

router = APIRouter(prefix="/api/v1/organization")
Role = Literal["admin", "operator", "reviewer", "auditor"]


def administrator(user=Depends(identity, scope="function")):
    if user.role != "admin":
        raise HTTPException(403)
    return user


class Change(BaseModel):
    role: Role
    active: bool
    previous_role: Role
    previous_active: bool


@router.get("/members")
def members(
    page: int = Query(1, ge=1, le=1000000),
    user=Depends(administrator, scope="function"),
    conn=Depends(db, scope="function"),
):
    rows = query(
        conn,
        """
        SELECT m.id,u.email,m.role,m.active,m.user_id=:actor AS own
        FROM memberships m JOIN users u ON u.id=m.user_id
        WHERE m.organization_id=:tenant ORDER BY u.email,m.id LIMIT 21 OFFSET :offset
        """,
        actor=user.actor,
        tenant=user.tenant,
        offset=(page - 1) * 20,
    ).all()
    return {"members": rows[:20], "more": len(rows) > 20, "page": page}


@router.patch("/members/{member_id}")
def update_member(
    member_id: UUID,
    change: Change,
    user=Depends(administrator, scope="function"),
    conn=Depends(db, scope="function"),
):
    # Serialize administrators' decisions, then re-check the actor after waiting.
    query(
        conn,
        "SELECT pg_advisory_xact_lock(hashtextextended(CAST(:tenant AS text), 0))",
        tenant=user.tenant,
    )
    current = query(
        conn,
        """SELECT role,active FROM memberships
        WHERE user_id=:actor AND organization_id=:tenant""",
        actor=user.actor,
        tenant=user.tenant,
    ).one()
    if not current.active or current.role != "admin":
        raise HTTPException(403)
    target = query(
        conn,
        """SELECT user_id,role,active FROM memberships
        WHERE id=:id AND organization_id=:tenant FOR UPDATE""",
        id=member_id,
        tenant=user.tenant,
    ).first()
    if not target:
        raise HTTPException(404)
    if target.user_id == user.actor:
        raise HTTPException(403)
    if (target.role, target.active) == (change.role, change.active):
        return {"ok": True}
    if (target.role, target.active) != (change.previous_role, change.previous_active):
        raise HTTPException(409)
    query(
        conn,
        "UPDATE memberships SET role=:role,active=:active WHERE id=:id AND organization_id=:tenant",
        role=change.role,
        active=change.active,
        id=member_id,
        tenant=user.tenant,
    )
    query(conn, "DELETE FROM sessions WHERE membership_id=:id", id=member_id)
    query(
        conn,
        """INSERT INTO member_access_events
        (organization_id,actor,member_id,old_role,new_role,was_active,is_active)
        VALUES(:tenant,:actor,:id,:old,:new,:was,:active)""",
        tenant=user.tenant,
        actor=user.actor,
        id=member_id,
        old=target.role,
        new=change.role,
        was=target.active,
        active=change.active,
    )
    return {"ok": True}

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..auth import identity
from ..db import db, query
from ..verification.api import run, safe
from . import schemas
from .domain import MOVES, TERMINAL, guidance, owner_write, validate_draft
from .service import (
    add_event,
    comparison,
    corrections,
    eligible,
    item_for,
    refs,
    replacement_targets,
)

router = APIRouter(prefix="/api/v1/exceptions")
User = Depends(identity, scope="function")
Conn = Depends(db, scope="function")
Page = Annotated[int, Query(ge=1, le=1000000)]
FIELDS = (
    "id",
    "supplier_id",
    "supplier",
    "archived",
    "run_id",
    "rule",
    "outcome",
    "severity",
    "created_at",
    "status",
    "assignee",
    "owner",
    "revision",
)


def summary(row):
    return {k: row[k] for k in FIELDS}


@router.get("", response_model=schemas.Queue)
def queue(
    user=User,
    conn=Conn,
    q: Annotated[str, Query(max_length=160)] = "",
    owner: str = "all",
    severity: Literal["high", "medium", "low", "all"] = "all",
    status: str = "unresolved",
    age: Annotated[int, Query(ge=0, le=36500)] = 0,
    sort: Literal["severity", "age", "supplier", "status"] = "severity",
    page: Page = 1,
):
    conditions = ["organization_id=:tenant"]
    params = {"tenant": user.tenant, "actor": user.actor, "offset": (page - 1) * 20}
    if q:
        conditions.append("strpos(lower(supplier),lower(:q))>0")
        params["q"] = q
    if owner == "unassigned":
        conditions.append("assignee IS NULL")
    elif owner == "mine":
        conditions.append("assignee=:actor")
    elif owner != "all":
        try:
            params["owner"] = UUID(owner)
        except ValueError as exc:
            raise HTTPException(422) from exc
        conditions.append("assignee=:owner")
    if severity != "all":
        conditions.append("severity=:severity")
        params["severity"] = severity
    if status == "unresolved":
        conditions.append("status NOT IN ('resolved','dismissed')")
    elif status in MOVES:
        conditions.append("status=:status")
        params["status"] = status
    elif status != "all":
        raise HTTPException(422)
    if age:
        conditions.append("created_at<=now()-:age * interval '1 day'")
        params["age"] = age
    where = " AND ".join(conditions)
    ordering = {
        "severity": "CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END",
        "age": "created_at",
        "supplier": "lower(supplier)",
        "status": "status",
    }[sort]
    rows = query(
        conn,
        f"SELECT * FROM exception_queue WHERE {where} ORDER BY {ordering},created_at,id LIMIT 20 OFFSET :offset",
        **params,
    )
    counts = query(
        conn,
        f"""SELECT count(*) AS total,count(*) FILTER(WHERE assignee=:actor) AS mine,count(*) FILTER(WHERE assignee IS NULL) AS unassigned FROM exception_queue WHERE {where}""",
        **params,
    ).one()
    return {"items": [summary(r) for r in rows], "counts": dict(counts), "page": page}


@router.get("/members", response_model=list[schemas.Member])
def members(
    user=User, conn=Conn, q: Annotated[str, Query(max_length=160)] = "", page: Page = 1
):
    return [
        dict(r)
        for r in query(
            conn,
            """SELECT u.id,u.email FROM memberships m JOIN users u ON u.id=m.user_id
    WHERE m.organization_id=:tenant AND m.active AND m.role IN ('admin','reviewer') AND strpos(lower(u.email),lower(:q))>0 ORDER BY u.email LIMIT 100 OFFSET :offset""",
            tenant=user.tenant,
            q=q,
            offset=(page - 1) * 100,
        )
    ]


@router.get("/{fid}", response_model=schemas.Detail, response_model_exclude_unset=True)
def detail(fid: UUID, user=User, conn=Conn, page: Page = 1):
    item = item_for(conn, user, fid)
    params = {"tenant": user.tenant, "fid": fid, "offset": (page - 1) * 20}
    editable = (
        user.role == "admin" or user.role == "reviewer" and user.actor == item.assignee
    )
    hist = query(
        conn,
        """SELECT r.seq,r.actor,u.email AS actor_name,r.created_at,r.kind,r.from_state,r.status,r.reason,r.assignee,a.email AS assigned_to,r.compared_run,r.correction_doc
    FROM verification_reviews r JOIN users u ON u.id=r.actor LEFT JOIN users a ON a.id=r.assignee WHERE r.organization_id=:tenant AND r.finding_id=:fid ORDER BY r.seq DESC LIMIT 20 OFFSET :offset""",
        **params,
    )
    history = [
        {
            k: v
            for k, v in h.items()
            if k != "reason" or user.role in {"admin", "reviewer"}
        }
        for h in hist
    ]
    drafts = (
        [
            dict(d)
            for d in query(
                conn,
                "SELECT revision,subject,message,actor,created_at FROM exception_drafts WHERE organization_id=:tenant AND finding_id=:fid ORDER BY revision DESC LIMIT 20 OFFSET :offset",
                **params,
            )
        ]
        if editable
        else []
    )
    versions = corrections(conn, item, 20, params["offset"])
    compared = query(
        conn,
        "SELECT compared_run,correction_doc FROM verification_reviews WHERE organization_id=:tenant AND finding_id=:fid AND kind='comparison' ORDER BY seq DESC LIMIT 1",
        **params,
    ).first()
    diff = (
        {
            **compared,
            "current": comparison(
                conn, item, compared.compared_run, compared.correction_doc
            ),
        }
        if compared
        else None
    )
    return {
        **summary(item),
        "evidence": refs(item.evidence),
        "guidance": guidance(item.rule, item.outcome, item.explanation),
        "history": history,
        "drafts": drafts,
        "corrections": [dict(v) for v in versions],
        "replacement_targets": replacement_targets(conn, item, versions)
        if page == 1 and user.role in {"admin", "operator"}
        else [],
        "comparison": diff,
        "transitions": sorted(MOVES[item.status])
        if editable and not item.archived
        else [],
        "can_edit": editable and not item.archived,
        "page": page,
    }


class Version(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    previous: int = Field(ge=0)


class Decision(Version):
    reason: str = Field(min_length=1, max_length=500)


class Assignment(Decision):
    assignee: UUID | None


class Transition(Decision):
    status: str = Field(max_length=40)
    reviewed_run: UUID | None = None


class Draft(Version):
    subject: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=1200)


def check(item, body):
    if item.revision != body.previous:
        raise HTTPException(409)
    if isinstance(body, Decision) and safe(body.reason) != body.reason:
        raise HTTPException(422)


@router.post("/{fid}/assignment", response_model=schemas.Event)
def assign(fid: UUID, body: Assignment, user=User, conn=Conn):
    if user.role != "admin":
        raise HTTPException(403)
    item = item_for(conn, user, fid, True)
    check(item, body)
    if item.status in TERMINAL or item.assignee == body.assignee:
        raise HTTPException(409)
    if body.assignee and not eligible(conn, user.tenant, body.assignee):
        raise HTTPException(422)
    status = item.status
    if status in {"assigned", "open"}:
        status = "assigned" if body.assignee else "open"
    return add_event(
        conn, user, item, "assignment", status, body.reason, assignee=body.assignee
    )


@router.post("/{fid}/drafts", response_model=schemas.DraftRevision)
def save_draft(fid: UUID, body: Draft, user=User, conn=Conn):
    item = item_for(conn, user, fid, True)
    owner_write(user, item)
    if item.status in TERMINAL:
        raise HTTPException(409)
    validate_draft(body, guidance(item.rule, item.outcome, item.explanation))
    params = {"tenant": user.tenant, "sid": item.supplier_id, "fid": fid}
    last = query(
        conn,
        "SELECT revision,subject,message FROM exception_drafts WHERE organization_id=:tenant AND finding_id=:fid ORDER BY revision DESC LIMIT 1",
        **params,
    ).first()
    if last and last.subject == body.subject and last.message == body.message:
        return {"revision": last.revision}
    if (last.revision if last else 0) != body.previous:
        raise HTTPException(409)
    return dict(
        query(
            conn,
            """INSERT INTO exception_drafts(organization_id,supplier_id,finding_id,revision,subject,message,actor)
    VALUES(:tenant,:sid,:fid,:rev,:subject,:message,:actor) RETURNING revision""",
            **params,
            rev=body.previous + 1,
            subject=body.subject,
            message=body.message,
            actor=user.actor,
        ).one()
    )


@router.post("/{fid}/compare", response_model=schemas.Event)
def compare(fid: UUID, body: Version, user=User, conn=Conn):
    item = item_for(conn, user, fid, True)
    owner_write(user, item)
    versions = corrections(conn, item)
    if (
        item.status in TERMINAL
        or not versions
        or versions[0].archived
        or versions[0].state not in {"needs_review", "failed"}
    ):
        raise HTTPException(409)
    doc = versions[0].document_id
    rid = run(item.supplier_id, user, conn)["id"]
    prev = query(
        conn,
        "SELECT seq,status,compared_run,correction_doc FROM verification_reviews WHERE organization_id=:tenant AND finding_id=:fid AND kind='comparison' ORDER BY seq DESC LIMIT 1",
        tenant=user.tenant,
        fid=fid,
    ).first()
    if prev and prev.compared_run == rid and prev.correction_doc == doc:
        return {"seq": prev.seq, "status": prev.status}
    check(item, body)
    return add_event(
        conn,
        user,
        item,
        "comparison",
        item.status,
        "Compared corrected document against the original finding.",
        rid=rid,
        doc=doc,
    )


@router.post("/{fid}/decision", response_model=schemas.Event)
def decide(fid: UUID, body: Transition, user=User, conn=Conn):
    item = item_for(conn, user, fid, True)
    owner_write(user, item)
    check(item, body)
    if body.status not in MOVES[item.status]:
        raise HTTPException(409)
    versions = corrections(conn, item)
    rid = None
    doc = None
    if body.status == "resolved" and versions:
        version = versions[0]
        doc = version.document_id
        rid = body.reviewed_run
        if not rid or version.archived or version.state != "needs_review":
            raise HTTPException(409)
        viewed = query(
            conn,
            "SELECT compared_run,correction_doc FROM verification_reviews WHERE organization_id=:tenant AND finding_id=:fid AND kind='comparison' ORDER BY seq DESC LIMIT 1",
            tenant=user.tenant,
            fid=fid,
        ).first()
        if (
            not viewed
            or viewed.compared_run != rid
            or viewed.correction_doc != doc
            or run(item.supplier_id, user, conn)["id"] != rid
        ):
            raise HTTPException(409)
        current = comparison(conn, item, rid, doc)
        if not current or any(
            r["requires_review"]
            or (item.rule == "requirement" and r["outcome"] != "received")
            for r in current
        ):
            raise HTTPException(409)
    return add_event(
        conn, user, item, "decision", body.status, body.reason, rid=rid, doc=doc
    )

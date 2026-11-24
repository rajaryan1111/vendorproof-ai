import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..auth import identity
from ..db import db, query
from ..suppliers import lookup
from .engine import VERSION, Document, evaluate
from .policy import Policy

router = APIRouter(prefix="/api/v1/suppliers/{sid}/verification")


def scope(user, sid):
    return {"tenant": user.tenant, "sid": sid}


def check_write(conn, user, sid, roles):
    if user.role not in roles:
        raise HTTPException(403)
    if lookup(conn, user, sid, True).archived:
        raise HTTPException(409)


def latest_policy(conn, params):
    return query(
        conn,
        "SELECT version,body,actor,created_at FROM verification_policies WHERE organization_id=:tenant AND supplier_id=:sid ORDER BY version DESC LIMIT 1",
        **params,
    ).first()


@router.get("/policy")
def policy(
    sid: UUID,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    lookup(conn, user, sid)
    row = latest_policy(conn, scope(user, sid))
    return dict(row) if row else {"version": 0, "body": Policy().model_dump()}


@router.put("/policy")
def configure(
    sid: UUID,
    body: Policy,
    previous: int = Query(ge=0),
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    check_write(conn, user, sid, {"admin"})
    params = scope(user, sid)
    current = latest_policy(conn, params)
    if (current.version if current else 0) != previous:
        raise HTTPException(409)
    if current and current.body == body.model_dump():
        return dict(current)
    return dict(
        query(
            conn,
            "INSERT INTO verification_policies(organization_id,supplier_id,version,body,actor) VALUES(:tenant,:sid,:v,CAST(:body AS jsonb),:actor) RETURNING version,body,actor,created_at",
            **params,
            v=previous + 1,
            body=body.model_dump_json(),
            actor=user.actor,
        ).one()
    )


@router.post("/runs")
def run(
    sid: UUID,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    check_write(conn, user, sid, {"admin", "reviewer", "operator"})
    params = scope(user, sid)
    config = latest_policy(conn, params)
    if not config:
        raise HTTPException(409)
    rows = query(
        conn,
        """SELECT d.id,d.digest,j.id AS attempt,j.state,j.report FROM documents d LEFT JOIN LATERAL
    (SELECT id,state,report FROM processing_attempts WHERE document_id=d.id AND organization_id=d.organization_id ORDER BY attempt DESC LIMIT 1) j ON true
    WHERE d.organization_id=:tenant AND d.supplier_id=:sid AND NOT d.archived ORDER BY d.id LIMIT 31""",
        **params,
    ).all()
    if len(rows) > 30:
        raise HTTPException(422)
    today = datetime.now(UTC).date()
    basis = [
        VERSION,
        today.isoformat(),
        config.version,
        [(str(r.id), r.digest, str(r.attempt), r.state) for r in rows],
    ]
    fingerprint = hashlib.sha256(json.dumps(basis).encode()).hexdigest()
    previous = query(
        conn,
        "SELECT id FROM verification_runs WHERE organization_id=:tenant AND supplier_id=:sid AND fingerprint=:fp",
        **params,
        fp=fingerprint,
    ).first()
    if previous:
        return {"id": previous.id}
    inventory, checklist, findings = evaluate(
        [Document.load(r) for r in rows], Policy.model_validate(config.body), today
    )
    rid = (
        query(
            conn,
            """INSERT INTO verification_runs(organization_id,supplier_id,policy_version,rule_version,as_of,fingerprint,inventory,checklist,actor)
      VALUES(:tenant,:sid,:v,:rule,:today,:fp,CAST(:inventory AS jsonb),CAST(:checklist AS jsonb),:actor) RETURNING id""",
            **params,
            v=config.version,
            rule=VERSION,
            today=today,
            fp=fingerprint,
            inventory=json.dumps(inventory),
            checklist=json.dumps(checklist),
            actor=user.actor,
        )
        .one()
        .id
    )
    for f in findings:
        query(
            conn,
            """INSERT INTO verification_findings(organization_id,supplier_id,run_id,rule,outcome,severity,explanation,quality,requires_review,evidence) VALUES(:tenant,:sid,:rid,:rule,:outcome,:severity,:explanation,:quality,:requires_review,CAST(:evidence AS jsonb))""",
            **params,
            rid=rid,
            **{**f, "evidence": json.dumps(f["evidence"])},
        )
    return {"id": rid}


@router.get("/runs")
def runs(
    sid: UUID,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    lookup(conn, user, sid)
    return [
        dict(r)
        for r in query(
            conn,
            "SELECT id,created_at,policy_version,rule_version,as_of FROM verification_runs WHERE organization_id=:tenant AND supplier_id=:sid ORDER BY created_at DESC,id DESC",
            **scope(user, sid),
        )
    ]


# Free text that resembles payment identifiers is withheld even in comparisons.
def safe(value):
    if value and re.search(
        r"(?:\d[ -]?){9,}|\b[A-Z]{2}\d{2}[ A-Z0-9]{10,}", value, re.IGNORECASE
    ):
        return "[restricted]"
    return value


@router.get("/runs/{rid}")
def details(
    sid: UUID,
    rid: UUID,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    params = scope(user, sid)
    row = query(
        conn,
        """SELECT r.*,p.body AS policy FROM verification_runs r JOIN verification_policies p ON p.organization_id=r.organization_id AND p.supplier_id=r.supplier_id AND p.version=r.policy_version
    WHERE r.organization_id=:tenant AND r.supplier_id=:sid AND r.id=:rid""",
        **params,
        rid=rid,
    ).first()
    if not row:
        raise HTTPException(404)
    active = {
        str(d.id)
        for d in query(
            conn,
            "SELECT id FROM documents WHERE organization_id=:tenant AND supplier_id=:sid AND NOT archived",
            **params,
        )
    }
    history = query(
        conn,
        """SELECT v.* FROM verification_reviews v JOIN verification_findings f ON v.finding_id=f.id AND v.organization_id=f.organization_id AND v.supplier_id=f.supplier_id
    WHERE f.organization_id=:tenant AND f.supplier_id=:sid AND f.run_id=:rid ORDER BY seq""",
        **params,
        rid=rid,
    )
    events = {}
    for h in history:
        item = {
            k: h[k]
            for k in ("seq", "actor", "created_at", "status", "kind", "from_state")
        }
        if user.role in {"admin", "reviewer"}:
            item["reason"] = safe(h.reason)
        events.setdefault(h.finding_id, []).append(item)
    managed = {
        r.id
        for r in query(
            conn,
            """SELECT f.id FROM verification_findings f WHERE f.run_id=:rid AND f.organization_id=:tenant AND (EXISTS(SELECT FROM verification_reviews r WHERE r.finding_id=f.id AND (r.kind!='decision' OR r.status IN ('in_progress','awaiting_supplier_response','awaiting_internal_review','reopened'))) OR EXISTS(SELECT FROM exception_corrections c WHERE c.finding_id=f.id) OR EXISTS(SELECT FROM exception_drafts d WHERE d.finding_id=f.id))""",
            **params,
            rid=rid,
        )
    }
    findings = []
    for f in query(
        conn,
        "SELECT * FROM verification_findings WHERE organization_id=:tenant AND supplier_id=:sid AND run_id=:rid ORDER BY rule,id",
        **params,
        rid=rid,
    ):
        evidence = []
        for ref in f.evidence:
            view = {k: v for k, v in ref.items() if k not in {"original", "normalized"}}
            if user.role == "admin" and ref["document"] in active and "original" in ref:
                view.update(
                    original=safe(ref["original"]),
                    normalized=safe(ref.get("normalized")),
                )
            evidence.append(view)
        audit = events.get(f.id, [])
        findings.append(
            {
                **f,
                "evidence": evidence,
                "history": audit,
                "managed": f.id in managed,
                "status": audit[-1]["status"]
                if audit
                else "needs_review"
                if f.requires_review
                else "open",
            }
        )
    return {**row, "findings": findings}


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["acknowledged", "dismissed", "resolved", "clarification_requested"]
    reason: str = Field(min_length=1, max_length=500)
    previous: int = Field(ge=0)


@router.post("/findings/{fid}/review")
def review(
    sid: UUID,
    fid: UUID,
    body: Review,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    check_write(conn, user, sid, {"admin", "reviewer"})
    params = scope(user, sid)
    target = query(
        conn,
        "SELECT run_id,requires_review FROM verification_findings WHERE id=:fid AND organization_id=:tenant AND supplier_id=:sid",
        **params,
        fid=fid,
    ).first()
    if not target:
        raise HTTPException(404)
    latest = query(
        conn,
        "SELECT id FROM verification_runs WHERE organization_id=:tenant AND supplier_id=:sid ORDER BY created_at DESC,id DESC LIMIT 1",
        **params,
    ).one()
    last = query(
        conn,
        "SELECT seq,status,from_state,kind FROM verification_reviews WHERE finding_id=:fid AND organization_id=:tenant AND supplier_id=:sid ORDER BY seq DESC LIMIT 1",
        **params,
        fid=fid,
    ).first()
    managed = (
        query(
            conn,
            """SELECT EXISTS(SELECT FROM verification_reviews WHERE finding_id=:fid AND organization_id=:tenant AND (kind!='decision' OR status IN ('open','assigned','in_progress','awaiting_supplier_response','awaiting_internal_review','reopened') OR from_state IS NOT NULL AND status IN ('resolved','dismissed'))) OR EXISTS(SELECT FROM exception_corrections WHERE finding_id=:fid AND organization_id=:tenant) OR EXISTS(SELECT FROM exception_drafts WHERE finding_id=:fid AND organization_id=:tenant) AS value""",
            fid=fid,
            **params,
        )
        .one()
        .value
    )
    if (
        managed
        or not target.requires_review
        or latest.id != target.run_id
        or body.previous != (last.seq if last else 0)
        or (last and last.status in {"resolved", "dismissed"})
    ):
        raise HTTPException(409)
    if safe(body.reason) != body.reason:
        raise HTTPException(422)
    return dict(
        query(
            conn,
            "INSERT INTO verification_reviews(organization_id,supplier_id,finding_id,actor,status,reason,from_state) VALUES(:tenant,:sid,:fid,:actor,:status,:reason,:old) RETURNING seq,status",
            **params,
            fid=fid,
            actor=user.actor,
            status=body.status,
            reason=body.reason,
            old=last.status if last else "open",
        ).one()
    )


@router.get("/findings/{fid}/sources/{index}")
def inspect_source(
    sid: UUID,
    fid: UUID,
    index: int,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    """Resolve an exact archived-run citation against a currently accessible original."""
    params = scope(user, sid)
    f = query(
        conn,
        "SELECT evidence FROM verification_findings WHERE id=:fid AND organization_id=:tenant AND supplier_id=:sid",
        fid=fid,
        **params,
    ).first()
    if not f or not 0 <= index < len(f.evidence):
        raise HTTPException(404)
    if user.role != "admin":
        raise HTTPException(403)
    ref = f.evidence[index]
    if "segment" not in ref:
        raise HTTPException(404)
    row = query(
        conn,
        """SELECT j.report FROM processing_attempts j JOIN documents d ON d.id=j.document_id AND d.organization_id=j.organization_id
    WHERE j.organization_id=:tenant AND j.supplier_id=:sid AND j.id=:attempt AND d.id=:doc AND d.digest=:digest AND NOT d.archived""",
        **params,
        attempt=ref["attempt"],
        doc=ref["document"],
        digest=ref["digest"],
    ).first()
    if not row:
        raise HTTPException(404)
    segment = row.report["pages"][ref["page"] - 1]["segments"][ref["segment"]]
    excerpt = segment["text"][ref["start"] : ref["end"]]
    if excerpt != ref["original"] or segment["method"] != ref["method"]:
        raise HTTPException(409)
    return {
        "excerpt": safe(excerpt),
        "page": ref["page"],
        "method": segment["method"],
        "bbox": segment["bbox"],
        "digest": ref["digest"],
    }

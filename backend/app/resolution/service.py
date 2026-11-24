from uuid import UUID

from fastapi import HTTPException

from ..db import query
from ..suppliers import lookup
from .domain import TERMINAL


def item_for(conn, user, fid, lock=False):
    params = {"tenant": user.tenant, "fid": fid}
    sql = """SELECT q.*,f.evidence,f.explanation,f.quality FROM exception_queue q JOIN verification_findings f ON f.id=q.id
    WHERE q.organization_id=:tenant AND q.id=:fid"""
    item = query(conn, sql, **params).first()
    if not item:
        raise HTTPException(404)
    if lock:
        if lookup(conn, user, item.supplier_id, True).archived:
            raise HTTPException(409)
        item = query(conn, sql, **params).one()
    return item


def refs(evidence):
    keys = (
        "document",
        "digest",
        "attempt",
        "field",
        "page",
        "segment",
        "method",
        "state",
    )
    return [{k: r[k] for k in keys if k in r} for r in evidence]


def corrections(conn, item, limit=1, offset=0):
    return query(
        conn,
        """SELECT c.document_id,c.actor,c.created_at,d.digest,d.replaces,d.archived,j.state,j.id AS attempt,j.error_code
    FROM exception_corrections c JOIN documents d ON d.id=c.document_id
    LEFT JOIN LATERAL(SELECT state,id,error_code FROM processing_attempts WHERE document_id=d.id ORDER BY attempt DESC LIMIT 1) j ON true
    WHERE c.finding_id=:fid AND c.organization_id=:tenant ORDER BY c.created_at DESC,c.document_id LIMIT :limit OFFSET :offset""",
        fid=item.id,
        tenant=item.organization_id,
        limit=limit,
        offset=offset,
    ).all()


def replacement_targets(conn, item, prior):
    """Offer active descendants of documents cited by this finding."""
    if prior:
        roots = [prior[0].document_id]
    elif item.rule == "requirement" and item.outcome == "missing_document":
        return []
    else:
        roots = [UUID(r["document"]) for r in item.evidence]
    return [
        r.id
        for r in query(
            conn,
            """WITH RECURSIVE versions AS (
        SELECT id,archived FROM documents WHERE organization_id=:tenant AND supplier_id=:sid AND id=ANY(CAST(:roots AS uuid[]))
        UNION SELECT d.id,d.archived FROM documents d JOIN versions v ON v.id=d.replaces WHERE d.organization_id=:tenant AND d.supplier_id=:sid)
        SELECT id FROM versions WHERE NOT archived ORDER BY id""",
            tenant=item.organization_id,
            sid=item.supplier_id,
            roots=roots,
        )
    ]


def validate_upload(conn, user, sid, fid, request_id, replaces, digest):
    if not request_id or not fid:
        raise HTTPException(422)
    item = item_for(conn, user, fid)
    if item.supplier_id != sid:
        raise HTTPException(404)
    previous = query(
        conn,
        """SELECT d.id,d.digest,d.replaces FROM exception_corrections c JOIN documents d ON d.id=c.document_id
    WHERE c.organization_id=:tenant AND c.finding_id=:fid AND c.request_id=:key""",
        tenant=user.tenant,
        fid=fid,
        key=request_id,
    ).first()
    if previous:
        if previous.digest != digest or previous.replaces != replaces:
            raise HTTPException(409)
        return previous.id
    if item.status in TERMINAL:
        raise HTTPException(409)
    prior = corrections(conn, item)
    targets = replacement_targets(conn, item, prior)
    if replaces not in targets and (targets or replaces):
        raise HTTPException(422)
    if (
        prior
        and prior[0].state != "failed"
        and not prior[0].archived
        and digest == prior[0].digest
    ):
        raise HTTPException(409)
    return None


def add_event(
    conn, user, item, kind, status, reason, assignee=None, rid=None, doc=None
):
    return dict(
        query(
            conn,
            """INSERT INTO verification_reviews(organization_id,supplier_id,finding_id,actor,from_state,status,kind,reason,assignee,compared_run,correction_doc)
    VALUES(:tenant,:sid,:fid,:actor,:old,:state,:kind,:reason,:assignee,:rid,:doc) RETURNING seq,status""",
            tenant=user.tenant,
            sid=item.supplier_id,
            fid=item.id,
            actor=user.actor,
            old=item.status,
            state=status,
            kind=kind,
            reason=reason,
            assignee=assignee,
            rid=rid,
            doc=doc,
        ).one()
    )


def comparison(conn, item, rid, doc):
    # Map the cited original to its replacement, retaining counterpart document and field.
    lineage = query(
        conn,
        """WITH RECURSIVE versions AS (
    SELECT id,replaces FROM documents WHERE organization_id=:tenant AND supplier_id=:sid AND id=:doc
    UNION ALL SELECT d.id,d.replaces FROM documents d JOIN versions v ON d.id=v.replaces WHERE d.organization_id=:tenant AND d.supplier_id=:sid)
    SELECT id FROM versions""",
        tenant=item.organization_id,
        sid=item.supplier_id,
        doc=doc,
    ).all()
    replaced = {str(r.id) for r in lineage}

    def signature(evidence):
        return {
            (str(doc) if r["document"] in replaced else r["document"], r.get("field"))
            for r in evidence
        }

    rows = query(
        conn,
        """SELECT id,rule,outcome,explanation,evidence,requires_review FROM verification_findings
    WHERE organization_id=:tenant AND supplier_id=:sid AND run_id=:rid AND rule=:rule
    AND EXISTS (SELECT FROM jsonb_array_elements(evidence) e WHERE e->>'document'=:version)""",
        tenant=item.organization_id,
        sid=item.supplier_id,
        rid=rid,
        rule=item.rule,
        version=str(doc),
    )
    matches = []
    for row in rows:
        if item.rule == "requirement":
            if row.explanation.partition(":")[0] != item.explanation.partition(":")[0]:
                continue
        elif item.rule in {"issue_date", "expiry_date"}:
            # Before correction a missing field has a document citation without a field.
            if {str(doc)} != {r["document"] for r in row.evidence}:
                continue
        elif signature(item.evidence) != signature(row.evidence):
            continue
        matches.append(
            {
                "id": row.id,
                "outcome": row.outcome,
                "evidence": refs(row.evidence),
                "requires_review": row.requires_review,
            }
        )
    return matches


def eligible(conn, tenant, actor: UUID):
    return query(
        conn,
        "SELECT user_id FROM memberships WHERE organization_id=:tenant AND user_id=:actor AND active AND role IN ('admin','reviewer') FOR SHARE",
        tenant=tenant,
        actor=actor,
    ).first()

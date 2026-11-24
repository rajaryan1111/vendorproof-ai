import hashlib
import os
import re
import subprocess
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from .auth import identity, writer
from .db import db, query
from .intelligence.child import command
from .intelligence.jobs import enqueue
from .resolution.service import validate_upload
from .safety import scan
from .suppliers import event, lookup

router = APIRouter(prefix="/api/v1/suppliers/{sid}/documents")
LIMIT = 5 * 1024 * 1024


class PrivateFiles:
    def __init__(self, root):
        self.root = root

    def path(self, tenant, key):
        return self.root / str(tenant) / str(key)

    def put(self, tenant, key, data):
        path = self.path(tenant, key)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with os.fdopen(
            os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
        ) as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        for directory in (path.parent, path.parent.parent):
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)


def validate_pdf(data, settings):
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise HTTPException(415)
    try:
        result = subprocess.run(
            command("app.intelligence.validate", settings),
            check=False,
            input=data,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=12,
            env={"PATH": os.defpath},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(503) from exc
    if result.returncode:
        raise HTTPException(422)


def document(conn, user, sid, key):
    row = query(
        conn,
        "SELECT * FROM documents WHERE id=:key AND organization_id=:tenant AND supplier_id=:sid AND NOT archived",
        key=key,
        tenant=user.tenant,
        sid=sid,
    ).first()
    if not row:
        raise HTTPException(404)
    return row


@router.get("")
def documents(
    sid: UUID,
    page: int = Query(1, ge=1, le=1000000),
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    lookup(conn, user, sid)
    return [
        {**r, "status": "stored"}
        for r in query(
            conn,
            "SELECT id,filename,bytes,created_at,replaces FROM documents WHERE organization_id=:tenant AND supplier_id=:sid AND NOT archived ORDER BY created_at DESC,id LIMIT 20 OFFSET :offset",
            offset=(page - 1) * 20,
            tenant=user.tenant,
            sid=sid,
        )
    ]


@router.post("", status_code=201)
async def upload(
    sid: UUID,
    request: Request,
    replaces: UUID | None = None,
    finding_id: UUID | None = None,
    request_id: UUID | None = None,
    x_filename: str = Header(max_length=160),
    user=Depends(writer, scope="function"),
    conn=Depends(db, scope="function"),
):
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_. -]*\.pdf", x_filename, re.IGNORECASE)
        or request.headers.get("content-type") != "application/pdf"
    ):
        raise HTTPException(415)
    if lookup(conn, user, sid).archived:
        raise HTTPException(409)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > LIMIT:
            raise HTTPException(413)
        data.extend(chunk)
    scanned = await run_in_threadpool(scan, data, request.app.state.settings)
    await run_in_threadpool(validate_pdf, data, request.app.state.settings)
    if lookup(conn, user, sid, True).archived:
        raise HTTPException(409)
    digest = hashlib.sha256(data).hexdigest()
    if finding_id or request_id:
        duplicate = validate_upload(
            conn, user, sid, finding_id, request_id, replaces, digest
        )
        if duplicate:
            return {"id": duplicate, "status": "stored"}
    if replaces:
        document(conn, user, sid, replaces)
        query(
            conn,
            "UPDATE documents SET archived=true WHERE id=:key AND organization_id=:tenant",
            key=replaces,
            tenant=user.tenant,
        )
    key = uuid4()
    query(
        conn,
        "INSERT INTO documents(id,organization_id,supplier_id,filename,bytes,digest,replaces,scanned_digest) VALUES(:key,:tenant,:sid,:name,:size,:digest,:replaces,:scan)",
        key=key,
        tenant=user.tenant,
        sid=sid,
        name=x_filename,
        size=len(data),
        digest=digest,
        scan=digest if scanned else None,
        replaces=replaces,
    )
    if finding_id:
        query(
            conn,
            """INSERT INTO exception_corrections(organization_id,supplier_id,finding_id,request_id,document_id,actor)
        VALUES(:tenant,:sid,:fid,:request,:doc,:actor)""",
            tenant=user.tenant,
            sid=sid,
            fid=finding_id,
            request=request_id,
            doc=key,
            actor=user.actor,
        )
    event(conn, user, sid, "Replaced document" if replaces else "Uploaded document")
    PrivateFiles(request.app.state.settings.storage_root).put(user.tenant, key, data)
    enqueue(conn, user.tenant, sid, key, user.actor)
    return {"id": key, "status": "stored"}


@router.get("/{key}")
def download(
    sid: UUID,
    key: UUID,
    request: Request,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    row = document(conn, user, sid, key)
    if user.role != "admin":
        raise HTTPException(403)
    settings = request.app.state.settings
    if settings.environment == "production" and row.scanned_digest != row.digest:
        raise HTTPException(409)
    with (
        PrivateFiles(settings.storage_root).path(user.tenant, key).open("rb") as stream
    ):
        data = stream.read(LIMIT + 1)
    if len(data) != row.bytes or hashlib.sha256(data).hexdigest() != row.digest:
        raise HTTPException(409)
    return Response(
        data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{row.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.delete("/{key}")
def archive(
    sid: UUID,
    key: UUID,
    user=Depends(writer, scope="function"),
    conn=Depends(db, scope="function"),
):
    if lookup(conn, user, sid, True).archived:
        raise HTTPException(409)
    document(conn, user, sid, key)
    query(
        conn,
        "UPDATE documents SET archived=true WHERE id=:key AND organization_id=:tenant",
        key=key,
        tenant=user.tenant,
    )
    event(conn, user, sid, "Archived document")
    return {"archived": True}

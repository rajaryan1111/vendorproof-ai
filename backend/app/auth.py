from hashlib import sha256
from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr

from .db import db, query

router = APIRouter(prefix="/api/v1")
hasher = PasswordHasher()
dummy = hasher.hash(token_urlsafe(32))


class Login(BaseModel):
    email: str = Field(max_length=254)
    workspace: str = Field(max_length=160)
    password: SecretStr = Field(max_length=256)


def digest(value):
    return sha256(value.encode()).hexdigest()


def identity(request: Request, conn=Depends(db, scope="function")):
    row = query(
        conn,
        """SELECT u.id AS actor,u.email,m.organization_id AS tenant,m.role,o.name AS workspace
    FROM sessions s JOIN memberships m ON m.id=s.membership_id JOIN users u ON u.id=m.user_id JOIN organizations o ON o.id=m.organization_id
    WHERE m.active AND s.digest=:digest AND s.expires_at>now()""",
        digest=digest(request.cookies.get("vp_session", "")),
    ).first()
    if not row:
        raise HTTPException(401)
    request.state.tenant = str(row.tenant)
    return row


def writer(user=Depends(identity, scope="function")):
    if user.role not in ("operator", "admin"):
        raise HTTPException(403)
    return user


@router.post("/login")
def login(
    body: Login,
    request: Request,
    response: Response,
    conn=Depends(db, scope="function"),
):
    attempts = (
        query(
            conn,
            """
        INSERT INTO login_limits VALUES(:key,now(),1)
        ON CONFLICT(key) DO UPDATE SET
          attempts=CASE WHEN login_limits.starts<now()-interval '5 minutes' THEN 1 ELSE login_limits.attempts+1 END,
          starts=CASE WHEN login_limits.starts<now()-interval '5 minutes' THEN now() ELSE login_limits.starts END
        RETURNING attempts""",
            key=digest(request.client.host),
        )
        .one()
        .attempts
    )
    if attempts > 60:
        return JSONResponse({"error": {"code": "http_429"}}, status_code=429)
    row = query(
        conn,
        "SELECT m.id,u.password_hash FROM memberships m JOIN users u ON u.id=m.user_id JOIN organizations o ON o.id=m.organization_id WHERE m.active AND email=:email AND o.name=:workspace FOR SHARE OF m",
        email=body.email.strip().lower(),
        workspace=body.workspace,
    ).first()
    try:
        hasher.verify(
            row.password_hash if row else dummy, body.password.get_secret_value()
        )
    except VerifyMismatchError:
        return JSONResponse({"error": {"code": "http_401"}}, status_code=401)
    if not row:
        raise HTTPException(401)
    token = token_urlsafe(32)
    query(
        conn,
        "DELETE FROM sessions WHERE digest=:digest OR expires_at<=now()",
        digest=digest(request.cookies.get("vp_session", "")),
    )
    query(
        conn,
        "INSERT INTO sessions VALUES(:digest,:membership,now()+interval '8 hours')",
        digest=digest(token),
        membership=row.id,
    )
    response.set_cookie(
        "vp_session",
        token,
        max_age=28800,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="strict",
    )
    return {"ok": True}


@router.get("/account")
def account(user=Depends(identity, scope="function")):
    return dict(user)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user=Depends(identity, scope="function"),
    conn=Depends(db, scope="function"),
):
    query(
        conn,
        "DELETE FROM sessions WHERE digest=:digest",
        digest=digest(request.cookies["vp_session"]),
    )
    response.delete_cookie(
        "vp_session",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return {"ok": True}

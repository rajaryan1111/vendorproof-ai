import json
import logging
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from .auth import router as auth_router
from .config import Settings
from .db import db, engine_for, query
from .documents import router as document_router
from .intelligence.jobs import router as processing_router
from .resolution.api import router as resolution_router
from .suppliers import router as supplier_router
from .verification.api import router as verification_router

logger = logging.getLogger("vendorproof.requests")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False


class Health(BaseModel):
    status: str


def failure(status: int, code: str, headers=None):
    return JSONResponse({"error": {"code": code}}, status_code=status, headers=headers)


def create_app(settings: Settings) -> FastAPI:
    api = FastAPI(
        title="VendorProof AI",
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )

    api.state.engine = engine_for(settings) if settings.database_url else None
    api.state.settings = settings
    api.include_router(verification_router)
    api.include_router(resolution_router)
    api.include_router(auth_router)
    api.include_router(processing_router)
    api.include_router(document_router)
    api.include_router(supplier_router)

    @api.get("/api/v1/health/db")
    def readiness(conn=Depends(db, scope="function")):
        query(conn, "SELECT 1").one()
        return Health(status="ok")

    @api.middleware("http")
    async def audit(request: Request, call_next):
        identifier = uuid4().hex
        started = monotonic()
        try:
            size = request.headers.get("content-length", "")
            limit = (
                5 * 1024**2
                if request.headers.get("content-type") == "application/pdf"
                else 65536
            )
            if size and (
                not size.isascii()
                or not size.isdecimal()
                or len(size) > 10
                or int(size) > limit
            ):
                response = failure(413, "request_too_large")
            elif (
                request.headers.get("transfer-encoding")
                and settings.environment == "production"
            ):
                response = failure(411, "length_required")
            elif request.method in {"POST", "PATCH", "DELETE", "PUT"} and (
                request.headers.get("X-VP-Request") != "1"
                or request.headers.get("origin") not in [None, *settings.cors_origins]
            ):
                response = failure(403, "forbidden_origin")
            else:
                response = await call_next(request)
        except Exception:  # noqa: BLE001 - boundary returns a redacted 500 response.
            response = failure(500, "internal_error")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = identifier
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.environment == "production":
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        logger.info(
            json.dumps(
                {
                    "event": "request",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "severity": "ERROR"
                    if response.status_code >= 500
                    else "WARNING"
                    if response.status_code >= 400
                    else "INFO",
                    "operation": request.method
                    + " "
                    + getattr(request.scope.get("route"), "path", "unmatched"),
                    "duration_ms": round((monotonic() - started) * 1000, 1),
                    "tenant": getattr(request.state, "tenant", None),
                    "request_id": identifier,
                    "status": response.status_code,
                }
            )
        )
        return response

    @api.exception_handler(HTTPException)
    async def http_error(request, exc):
        return failure(exc.status_code, f"http_{exc.status_code}", exc.headers)

    @api.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return failure(422, "invalid_request")

    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["X-VP-Request", "Content-Type", "X-Filename"],
        allow_credentials=True,
    )

    @api.get("/api/v1/health", response_model=Health)
    async def health():
        return Health(status="ok")

    return api


app = create_app(Settings())

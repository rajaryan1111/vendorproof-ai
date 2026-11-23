import json
import logging
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
    api = FastAPI(title="VendorProof AI")

    api.state.engine = engine_for(settings) if settings.database_url else None
    api.state.settings = settings
    api.include_router(verification_router)
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
        try:
            if request.method in {"POST", "PATCH", "DELETE", "PUT"} and (
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
        logger.info(
            json.dumps(
                {
                    "event": "request",
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

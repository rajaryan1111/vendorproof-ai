import json
import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from .config import Settings

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

    @api.middleware("http")
    async def audit(request: Request, call_next):
        identifier = uuid4().hex
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - boundary returns a redacted 500 response.
            response = failure(500, "internal_error")
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
        CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET"]
    )

    @api.get("/api/v1/health", response_model=Health)
    async def health():
        return Health(status="ok")

    return api


app = create_app(Settings())

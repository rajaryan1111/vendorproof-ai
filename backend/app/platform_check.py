"""No-data entry point for measuring the parser boundary on a hosting platform."""

import asyncio
import os
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .intelligence.child import isolated_command


@asynccontextmanager
async def lifespan(app):
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            isolated_command("app.intelligence.probe"),
            capture_output=True,
            env={"PATH": os.defpath},
            timeout=15,
            check=False,
        )
        isolated = result.returncode == 0 and result.stdout.strip() == b"parser-ready"
    except (OSError, subprocess.TimeoutExpired):
        isolated = False
    app.state.isolated = isolated
    yield


app = FastAPI(openapi_url=None, lifespan=lifespan)
headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


@app.get("/api/v1/health")
def platform_health():
    return JSONResponse(
        {"status": "validation_only", "parser_probe_passed": app.state.isolated},
        headers=headers,
    )


@app.api_route(
    "/{path:path}", methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
def unavailable(path: str):
    return JSONResponse(
        {"error": {"code": "workspace_offline"}}, status_code=503, headers=headers
    )

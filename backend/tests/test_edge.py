"""Verify the release frontend and API over loopback TLS with an ephemeral test certificate."""

import os
import re
import secrets
import ssl
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

from app.config import Settings
from app.db import engine_for
from app.provision import provision


def test_https_release(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    root = backend.parent
    cert, key = tmp_path / "cert.pem", tmp_path / "private.key"
    config = tmp_path / "openssl.conf"
    config.write_text(
        "[req]\ndistinguished_name=dn\nx509_extensions=extensions\nprompt=no\n[dn]\nCN=localhost\n[extensions]\nsubjectAltName=DNS:localhost\nbasicConstraints=critical,CA:TRUE\n"
    )
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-days",
            "1",
            "-config",
            str(config),
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    caddyfile = tmp_path / "Caddyfile"
    production = (root / "deploy/Caddyfile").read_text()
    caddyfile.write_text(
        production.replace(
            "admin off", "admin off\n auto_https disable_redirects"
        ).replace(
            "{$VP_SITE} {",
            '{$VP_SITE} {\n bind 127.0.0.1\n tls "'
            + str(cert)
            + '" "'
            + str(key)
            + '"',
        )
    )
    base = "https://localhost:58443"
    env = {
        **os.environ,
        "VP_SITE": "localhost:58443",
        "VP_API_UPSTREAM": "127.0.0.1:58002",
        "VP_STATIC_ROOT": str(root / "frontend/dist"),
        "VP_DATABASE_URL": os.environ["VP_TEST_DATABASE_URL"],
        "VP_ENVIRONMENT": "testing",
        "VP_COOKIE_SECURE": "true",
        "VP_CORS_ORIGINS": '["https://localhost:58443"]',
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    workspace = uuid4().hex
    email = workspace + "@example.invalid"
    password = secrets.token_urlsafe(24)
    engine = engine_for(Settings(database_url=env["VP_DATABASE_URL"]))
    with engine.begin() as conn:
        provision(conn, workspace, email, password, "admin")
    engine.dispose()
    with subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            "58002",
            "--no-access-log",
        ],
        cwd=backend,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) as api:
        try:
            with subprocess.Popen(
                ["caddy", "run", "--config", str(caddyfile), "--adapter", "caddyfile"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ) as edge:
                try:
                    with httpx.Client(
                        base_url=base,
                        verify=ssl.create_default_context(cafile=str(cert)),
                        trust_env=False,
                        timeout=3,
                    ) as client:
                        for _ in range(100):
                            assert edge.poll() is None and api.poll() is None
                            try:
                                if client.get("/api/v1/health/db").is_success:
                                    break
                            except httpx.TransportError:
                                pass
                            time.sleep(0.1)
                        else:
                            raise AssertionError("TLS readiness timeout")
                        page = client.get("/exceptions")
                        assert (
                            page.status_code == 200
                            and "frame-ancestors 'none'"
                            in page.headers["content-security-policy"]
                        )
                        assert "max-age" in page.headers["strict-transport-security"]
                        js = re.search(r'src="(/assets/[^"]+\.js)"', page.text)[1]
                        assert client.get(js).is_success
                        assert client.get("/api/v1/account").status_code == 401
                        login = client.post(
                            "/api/v1/login",
                            headers={"X-VP-Request": "1", "origin": base},
                            json={
                                "workspace": workspace,
                                "email": email,
                                "password": password,
                            },
                        )
                        assert login.is_success
                        for flag in ["HttpOnly", "Secure", "SameSite=strict"]:
                            assert flag.lower() in login.headers["set-cookie"].lower()
                        assert (
                            client.get("/api/v1/account").json()["workspace"]
                            == workspace
                        )
                finally:
                    edge.terminate()
        finally:
            api.terminate()

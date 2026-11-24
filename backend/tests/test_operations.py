import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings
from app.safety import scan
from evaluation.v1.fixtures import make_pdf


def test_production_fails_closed(tmp_path):
    for options in (
        {},
        {"cookie_secure": False},
        {
            "database_url": "postgresql+psycopg://localhost/test",
            "storage_root": tmp_path,
            "scanner_socket": tmp_path / "sock",
            "cors_origins": ["http://localhost"],
        },
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, environment="production", **options)
    settings = Settings(environment="testing", scanner_socket=tmp_path / "absent")
    with pytest.raises(HTTPException) as err:
        scan(b"synthetic", settings)
    assert err.value.status_code == 503


def test_real_clamav_ingress(accounts, tmp_path):
    # A private synthetic signature exercises a real engine without a live threat sample.
    import tempfile

    with tempfile.TemporaryDirectory(dir="/tmp") as short:
        root = Path(short)
        marker = b"VendorProofHarmlessScannerFixture"
        (root / "synthetic.ndb").write_text(
            "VendorProof.Test:0:*:" + marker.hex() + "\n"
        )
        path = root / "clam.sock"
        conf = root / "clamd.conf"
        conf.write_text(
            f"Foreground yes\nDatabaseDirectory {root}\nLocalSocket {path}\nLogFile {root}/scanner.log\n"
        )
        binary = shutil.which("clamd") or next(
            (
                p
                for p in ("/usr/sbin/clamd", "/opt/homebrew/opt/clamav/sbin/clamd")
                if os.path.isfile(p)
            ),
            None,
        )
        assert binary, "Install clamav-daemon for the safety suite"
        proc = subprocess.Popen(
            [binary, "-c", str(conf)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                if path.exists():
                    break
                assert proc.poll() is None
                time.sleep(0.05)
            client = accounts["admin"]
            client.app.state.settings.scanner_socket = path
            sid = client.post(
                "/api/v1/suppliers", json={"name": "Synthetic scanner"}
            ).json()["id"]
            url = f"/api/v1/suppliers/{sid}/documents"
            clean = make_pdf({"pages": ["Synthetic registration"], "media": ["native"]})
            headers = {"Content-Type": "application/pdf", "X-Filename": "test.pdf"}
            marked = clean.replace(b"%%EOF", b"%" + marker + b"\n%%EOF")
            assert client.post(url, content=marked, headers=headers).status_code == 422
            assert client.get(url).json() == []
            assert client.post(url, content=clean, headers=headers).is_success
            from sqlalchemy import text

            with client.app.state.engine.begin() as conn:
                assert conn.execute(
                    text(
                        "SELECT digest=scanned_digest FROM documents WHERE supplier_id=:sid"
                    ),
                    {"sid": sid},
                ).scalar_one()
            proc.terminate()
            proc.wait(timeout=10)
            assert client.post(url, content=clean, headers=headers).status_code == 503
            assert len(client.get(url).json()) == 1
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)


def test_concurrent_uploads_and_job_claim(accounts):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import UUID

    from app.intelligence.worker import run_one
    from app.operations import retention_inventory

    client = accounts["admin"]
    account = client.get("/api/v1/account").json()
    sid = client.post("/api/v1/suppliers", json={"name": "Synthetic intake"}).json()[
        "id"
    ]
    url = f"/api/v1/suppliers/{sid}/documents"
    data = make_pdf({"pages": ["Supplier agreement"], "media": ["native"]})
    with ThreadPoolExecutor(4) as pool:
        started = time.perf_counter()
        ids = list(
            pool.map(
                lambda i: client.post(
                    url,
                    content=data,
                    headers={
                        "Content-Type": "application/pdf",
                        "X-Filename": f"fixture-{i}.pdf",
                    },
                ).json()["id"],
                range(4),
            )
        )
        print(
            "4 concurrent small native uploads in seconds",
            round(time.perf_counter() - started, 3),
        )
        assert len(set(ids)) == 4
        job = UUID(client.get(url + "/" + ids[0] + "/processing").json()[0]["id"])
        state = client.app.state
        assert sorted(
            pool.map(lambda _: run_one(state.engine, state.settings, job), range(2))
        ) == [False, True]
    with state.engine.connect() as conn:
        counts = retention_inventory(conn, account["tenant"])
        assert counts["documents"] == 4 and counts["processing_attempts"] == 4
    assert client.get(url + "?page=2").json() == []


def test_parser_deployment_boundary(tmp_path):
    import sys

    from app.intelligence.child import command

    settings = Settings(environment="testing").model_copy(
        update={"environment": "production"}
    )
    invocation = command("app.intelligence.probe", settings)
    assert invocation[0] == "/usr/bin/bwrap" and "--unshare-all" in invocation
    if sys.platform.startswith("linux"):
        result = subprocess.run(
            invocation,
            capture_output=True,
            env={"PATH": os.defpath},
            timeout=15,
            check=False,
        )
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert result.stdout.strip() == b"parser-ready"
    else:
        with pytest.raises(ValidationError):
            Settings(
                environment="production",
                cookie_secure=True,
                database_url=os.environ["VP_TEST_DATABASE_URL"],
                storage_root=tmp_path,
                scanner_socket=tmp_path / "socket",
                cors_origins=["https://test.invalid"],
            )

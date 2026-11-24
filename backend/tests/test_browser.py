"""Live local acceptance. Requires Chrome, npm ci, and a migrated disposable DB."""

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
from psycopg import sql
from sqlalchemy.engine import make_url

from app.config import Settings
from app.db import engine_for
from app.main import create_app
from app.operations import probes
from app.provision import provision
from app.recovery import backup, db_params, digest, restore
from evaluation.v1.fixtures import make_pdf


def start(command, cwd, env, url):
    proc = subprocess.Popen(
        command, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        for _ in range(100):
            if proc.poll() is not None:
                raise RuntimeError("Service exited before readiness")
            try:
                with urlopen(url, timeout=1):
                    return proc
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("Readiness timeout")
    except BaseException:
        stop(proc)
        raise


def stop(proc):
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture
def drill_databases(monkeypatch):
    original = Settings(database_url=os.environ["VP_TEST_DATABASE_URL"])
    params = db_params(original)
    names = ["vp_drill_" + uuid4().hex for _ in range(2)]
    with psycopg.connect(**params, autocommit=True) as conn:
        for name in names:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            urls = [
                make_url(str(original.database_url))
                .set(database=n)
                .render_as_string(hide_password=False)
                for n in names
            ]
            monkeypatch.setenv("VP_DATABASE_URL", urls[0])
            command.upgrade(Config("alembic.ini"), "head")
            yield urls
        finally:
            for name in names:
                conn.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(name)
                    )
                )


@pytest.mark.parametrize("width", [1280, 390], ids=["desktop", "mobile"])
def test_browser_workflow(tmp_path, drill_databases, width):
    backend = Path(__file__).resolve().parents[1]
    front = "http://localhost:55173"
    api = "http://localhost:58001/api/v1"
    env = {
        **os.environ,
        "VP_DATABASE_URL": drill_databases[0],
        "VP_ENVIRONMENT": "testing",
        "VP_COOKIE_SECURE": "false",
        "VP_STORAGE_ROOT": str(tmp_path / "source-objects"),
        "VP_CORS_ORIGINS": '["http://localhost:55173"]',
        "VITE_API_BASE_URL": api,
    }
    workspace = uuid4().hex
    email = uuid4().hex + "@example.invalid"
    password = secrets.token_urlsafe(24)
    engine = engine_for(Settings(database_url=env["VP_DATABASE_URL"]))
    with engine.begin() as conn:
        provision(conn, workspace, email, password, "admin")
        provision(conn, workspace, "review" + email, password, "reviewer")
        provision(conn, workspace + "2", "other" + email, password, "admin")
    engine.dispose()

    def server():
        return start(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--port",
                "58001",
                "--no-access-log",
            ],
            backend,
            env,
            api + "/health/db",
        )

    api_proc = server()
    try:
        web = start(
            ["node", "node_modules/vite/bin/vite.js", "--port", "55173"],
            backend.parent / "frontend",
            env,
            front,
        )
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome")
                page = browser.new_page(viewport={"width": width, "height": 844})
                page.goto(front)
                page.get_by_label("Workspace").fill(workspace)
                page.get_by_label("Email").fill(email)
                page.get_by_label("Password").fill(password)
                page.get_by_role("button", name="Sign in").click()
                page.get_by_role("link", name="Suppliers", exact=True).click()
                page.get_by_text("Create supplier", exact=True).click()
                page.get_by_role("button", name="Save supplier").click()
                assert not page.get_by_label("Supplier name").evaluate(
                    "el=>el.validity.valid"
                )
                page.get_by_label("Supplier name").fill("Synthetic supplier")
                page.get_by_role("button", name="Save supplier").click()
                page.get_by_role("link", name="Supplier directory").click()
                page.get_by_role("link", name="Synthetic supplier").click()
                page.get_by_text("Edit supplier", exact=True).click()
                page.get_by_label("Supplier name").fill("Updated synthetic supplier")
                page.get_by_role("button", name="Save supplier").click()
                pdf = make_pdf(
                    {
                        "pages": ["Insurance certificate\nPolicy number: SYNTH-42"],
                        "media": ["scan"],
                    }
                )
                page.get_by_label("PDF document").set_input_files(
                    {
                        "name": "synthetic.pdf",
                        "mimeType": "application/pdf",
                        "buffer": pdf,
                    }
                )
                page.get_by_role("button", name="Upload PDF").click()
                expect(page.get_by_text("synthetic.pdf", exact=True)).to_be_visible()
                link = page.get_by_role("link", name="Download")
                url = link.get_attribute("href")
                assert page.request.get(url).body() == pdf
                job = page.request.get(url + "/processing").json()[0]["id"]
                subprocess.run(
                    [sys.executable, "-m", "app.intelligence.worker", "--job", job],
                    cwd=backend,
                    env=env,
                    check=True,
                    timeout=120,
                )
                expect(
                    page.get_by_role("button", name="View extraction 1")
                ).to_be_visible(timeout=12000)
                page.get_by_role("button", name="View extraction 1").click()
                expect(
                    page.get_by_role("heading", name="Extraction candidates")
                ).to_be_visible()
                assert (
                    page.request.get(url + "/processing/" + job).json()[
                        "classification"
                    ]["category"]
                    == "insurance"
                )
                other = browser.new_context()
                assert other.request.post(
                    api + "/login",
                    headers={"X-VP-Request": "1"},
                    data={
                        "workspace": workspace + "2",
                        "email": "other" + email,
                        "password": password,
                    },
                ).ok
                assert other.request.get(url).status == 404
                assert other.request.get(url + "/processing/" + job).status == 404
                supplier_url = url.split("/documents/")[0]
                assert other.request.get(supplier_url).status == 404
                verify = supplier_url + "/verification"
                # Existing scan has already passed the Phase 2 browser assertions.
                for n, (transcript, media) in enumerate(
                    [
                        (
                            [
                                "Company registration certificate\nLegal name: Synthetic Vale Pvt Ltd"
                            ],
                            ["native"],
                        ),
                        (
                            [
                                "Tax registration document\nRegistered business name: Synthetic Vale Private Limited"
                            ],
                            ["native"],
                        ),
                        (
                            [
                                "Bank verification letter\nAccount holder: Synthetic Rival Ltd"
                            ],
                            ["native"],
                        ),
                        (
                            ["Insurance certificate\nExpiry date: 2020-01-01", "x"],
                            ["native", "degraded"],
                        ),
                    ]
                ):
                    data = make_pdf({"pages": transcript, "media": media})
                    uploaded = page.request.post(
                        supplier_url + "/documents",
                        headers={
                            "X-VP-Request": "1",
                            "Content-Type": "application/pdf",
                            "X-Filename": f"synthetic-{n}.pdf",
                        },
                        data=data,
                    )
                    assert uploaded.status == 201
                    processing = (
                        supplier_url
                        + "/documents/"
                        + uploaded.json()["id"]
                        + "/processing"
                    )
                    job_id = page.request.get(processing).json()[0]["id"]
                    subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "app.intelligence.worker",
                            "--job",
                            job_id,
                        ],
                        cwd=backend,
                        env=env,
                        check=True,
                        timeout=120,
                    )
                page.reload()
                page.get_by_text("Configure requirements", exact=True).click()
                page.get_by_label("Require agreement", exact=True).check()
                page.get_by_label("Require insurance", exact=True).check()
                page.locator('input[name="insuranceexpiry"]').check()
                page.locator('input[name="aliases"]').check()
                page.get_by_role("button", name="Save policy version").click()
                page.get_by_role("button", name="Run verification").click()
                expect(
                    page.get_by_role("heading", name="Findings", exact=True)
                ).to_be_visible()
                run_id = page.request.get(verify + "/runs").json()[0]["id"]
                result_url = verify + "/runs/" + run_id
                findings = page.request.get(result_url).json()["findings"]

                def get(rule, outcome):
                    return next(
                        f
                        for f in findings
                        if (f["rule"], f["outcome"]) == (rule, outcome)
                    )

                assert len(get("name", "normalized_match")["evidence"]) == 2
                assert len(get("bank_holder", "conflict")["evidence"]) == 2
                assert (
                    get("expiry_date", "expired")["evidence"][0]["original"]
                    == "2020-01-01"
                )
                assert (
                    "agreement" in get("requirement", "missing_document")["explanation"]
                )
                assert any(
                    f["quality"] == "insufficient" and f["rule"] == "page_quality"
                    for f in findings
                )
                conflict = get("bank_holder", "conflict")
                source_index = next(
                    i
                    for i, r in enumerate(conflict["evidence"])
                    if r["field"] != "account_holder"
                )
                source_url = (
                    verify + "/findings/" + conflict["id"] + f"/sources/{source_index}"
                )
                assert (
                    page.request.get(source_url).json()["excerpt"]
                    == conflict["evidence"][source_index]["original"]
                )
                assert other.request.get(source_url).status == 404
                panel = (
                    page.locator("article")
                    .filter(
                        has=page.get_by_role(
                            "heading", name="bank holder · conflict", exact=True
                        )
                    )
                    .first
                )
                panel.get_by_text("Source evidence (2)", exact=True).click()
                panel.get_by_role("button", name="Open cited span").first.click()
                expect(panel.get_by_role("status")).to_contain_text("Page 1")

                repeat = page.request.post(
                    verify + "/runs", headers={"X-VP-Request": "1"}
                )
                assert repeat.json()["id"] == run_id
                assert other.request.get(result_url).status == 404
                viewer = browser.new_context(viewport={"width": width, "height": 844})
                assert viewer.request.post(
                    api + "/login",
                    headers={"X-VP-Request": "1"},
                    data={
                        "workspace": workspace,
                        "email": "review" + email,
                        "password": password,
                    },
                ).ok
                assert viewer.request.get(source_url).status == 403
                reviewed = viewer.new_page()
                reviewed.goto(page.url)
                expect(
                    reviewed.get_by_role("heading", name="Findings", exact=True)
                ).to_be_visible()
                target = reviewed.locator("article").filter(
                    has=reviewed.get_by_role(
                        "heading", name="expiry date · expired", exact=True
                    )
                )
                target.get_by_text("Source evidence (1)", exact=True).click()
                target.get_by_label("Review action").select_option("dismissed")
                target.get_by_label("Reason or supporting information").fill(
                    "Synthetic renewal inspected in procurement."
                )
                target.get_by_role("button", name="Record review").click()
                expect(
                    target.get_by_text("Synthetic renewal inspected", exact=False)
                ).to_be_visible()
                masked = viewer.request.get(result_url).json()
                assert all(
                    "original" not in ref and "normalized" not in ref
                    for f in masked["findings"]
                    for ref in f["evidence"]
                )
                audit = next(
                    f
                    for f in masked["findings"]
                    if f["id"] == get("expiry_date", "expired")["id"]
                )["history"][0]
                assert (
                    audit["status"] == "dismissed"
                    and audit["actor"]
                    and audit["created_at"]
                )
                supplier_page = page.url
                fid = conflict["id"]
                exception_url = api + "/exceptions/" + fid
                exception_page = front + "/exceptions/" + fid
                page.locator('a[href="/exceptions/' + fid + '"]').click()
                expect(page.get_by_role("heading", name="Ownership")).to_be_visible()
                page.get_by_label("Assign to", exact=True).select_option(
                    label="review" + email
                )
                page.get_by_label("Assignment reason").fill(
                    "Review the cited account holder discrepancy."
                )
                page.get_by_role("button", name="Record assignment").click()
                expect(
                    page.get_by_text("Assignment recorded", exact=True)
                ).to_be_visible()
                reviewed.get_by_role("link", name="Exceptions", exact=True).click()
                reviewed.get_by_label("Ownership").select_option("mine")
                reviewed.get_by_role("button", name="Apply filters").click()
                expect(
                    reviewed.get_by_text("1 matching · 1 assigned to me · 0 unassigned")
                ).to_be_visible()
                reviewed.get_by_role(
                    "link", name="Updated synthetic supplier · bank holder"
                ).click()
                expect(reviewed).to_have_url(exception_page)
                reviewed.get_by_text("Original evidence (2)").click()
                expect(
                    reviewed.get_by_text("Verification run " + run_id)
                ).to_be_visible()
                expect(
                    reviewed.get_by_text(
                        "Please clarify the account holder name and provide supporting documentation.",
                        exact=True,
                    ).first
                ).to_be_visible()
                reviewed.get_by_role("button", name="Save draft").click()
                expect(
                    reviewed.get_by_text("Revision 1 ·", exact=False)
                ).to_be_visible()
                reviewed.get_by_label("Draft subject").select_option(index=1)
                reviewed.get_by_role(
                    "button", name="Thank you for your assistance."
                ).click()
                reviewed.get_by_role("button", name="Save draft").click()
                expect(
                    reviewed.get_by_text("Revision 2 ·", exact=False)
                ).to_be_visible()
                old_bank = next(
                    r["document"]
                    for r in conflict["evidence"]
                    if r["field"] == "account_holder"
                )
                page.get_by_label("Document to replace").select_option(old_bank)
                page.get_by_label("Corrected PDF").set_input_files(
                    {
                        "name": "corrected-bank.pdf",
                        "mimeType": "application/pdf",
                        "buffer": make_pdf(
                            {
                                "pages": [
                                    "Bank verification letter\nAccount holder: Synthetic Vale Private Limited"
                                ],
                                "media": ["native"],
                            }
                        ),
                    }
                )
                page.get_by_label("Confirm corrected version").check()
                page.get_by_role("button", name="Upload correction").click()
                expect(
                    page.get_by_text("Correction queued", exact=True)
                ).to_be_visible()
                version = page.request.get(exception_url).json()["corrections"][0]
                assert version["state"] == "queued" and version["replaces"] == old_bank
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "app.intelligence.worker",
                        "--job",
                        version["attempt"],
                    ],
                    cwd=backend,
                    env=env,
                    check=True,
                    timeout=120,
                )
                reviewed.get_by_role("button", name="Refresh exception").click()
                reviewed.get_by_role("button", name="Rerun and compare").click()
                expect(
                    reviewed.get_by_role("heading", name="Verification comparison")
                ).to_be_visible()
                expect(
                    reviewed.get_by_text("Current outcome ·", exact=False)
                ).to_contain_text("match")
                predecision = viewer.request.get(exception_url).json()
                assert (
                    predecision["status"] == "assigned"
                    and len(predecision["comparison"]["current"]) == 1
                )
                reviewed.get_by_label("Next state").select_option("resolved")
                reviewed.get_by_label("Decision reason").fill(
                    "Reviewed the corrected holder comparison and cited document versions."
                )
                reviewed.get_by_label("I reviewed the available evidence").check()
                reviewed.get_by_role("button", name="Record decision").click()
                expect(
                    reviewed.get_by_text("Decision recorded", exact=True)
                ).to_be_visible()
                history = viewer.request.get(exception_url).json()["history"]
                assert [h["kind"] for h in history] == [
                    "decision",
                    "comparison",
                    "assignment",
                ]
                assert (
                    history[0]["status"] == "resolved"
                    and history[0]["from_state"] == "assigned"
                )
                assert all(h["created_at"] and h["actor"] for h in history)
                assert other.request.get(exception_url).status == 404
                assert (
                    other.request.get(
                        supplier_url + "/documents/" + version["document_id"]
                    ).status
                    == 404
                )
                assert (
                    other.request.post(
                        exception_url + "/drafts",
                        headers={"X-VP-Request": "1"},
                        data={
                            "previous": 0,
                            "subject": "Synthetic",
                            "message": "Synthetic",
                        },
                    ).status
                    == 404
                )
                assert (
                    page.request.get(supplier_url + "/documents/" + old_bank).status
                    == 404
                )
                for active in (page, reviewed):
                    assert active.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    )
                if width == 1280:
                    reviewed.set_viewport_size({"width": 768, "height": 1024})
                    assert reviewed.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    )
                    fresh = viewer.new_page()
                    fresh.set_viewport_size({"width": 768, "height": 1024})
                    fresh.goto(front + "/exceptions")
                    expect(
                        fresh.get_by_role("heading", name="Exception queue")
                    ).to_be_visible()
                    fresh.keyboard.press("Tab")
                    expect(
                        fresh.get_by_role("link", name="Skip to workspace")
                    ).to_be_focused()
                    fresh.keyboard.press("Enter")
                    expect(fresh.locator("#workspace")).to_be_focused()
                    fresh.close()
                    checkpoints = {}
                    for operation, endpoint in {
                        "queue": api + "/exceptions",
                        "directory": api + "/suppliers",
                        "dashboard": api + "/dashboard",
                        "comparison": exception_url,
                    }.items():
                        elapsed = []
                        for _ in range(15):
                            start_at = time.perf_counter()
                            response = page.request.get(endpoint)
                            assert response.ok
                            elapsed.append((time.perf_counter() - start_at) * 1000)
                        checkpoints[operation] = (
                            round(sorted(elapsed)[7], 1),
                            round(max(elapsed), 1),
                            len(response.body()),
                        )
                    print("release probe (median_ms, max_ms, bytes):", checkpoints)
                    source = Settings(
                        database_url=drill_databases[0],
                        storage_root=Path(env["VP_STORAGE_ROOT"]),
                    )
                    restored = Settings(
                        database_url=drill_databases[1],
                        storage_root=tmp_path / "restored-objects",
                    )
                    keyfile = tmp_path / "recovery-key"
                    subprocess.run(
                        ["age-keygen", "-o", str(keyfile)],
                        check=True,
                        stderr=subprocess.DEVNULL,
                    )
                    recipient = subprocess.check_output(
                        ["age-keygen", "-y", str(keyfile)], text=True
                    ).strip()
                    started = time.perf_counter()
                    vault = tmp_path / "backups"
                    vault.mkdir(mode=0o700)
                    old = vault / (
                        "vendorproof-20000101T000000Z-" + uuid4().hex + ".age"
                    )
                    old.touch()
                    os.utime(old, (1, 1))
                    archive = backup(source, vault, recipient, 14)
                    assert not old.exists()
                    with pytest.raises(ValueError, match="digest"):
                        restore(
                            restored, archive, keyfile, restored.storage_root, "0" * 64
                        )
                    backup_seconds = time.perf_counter() - started
                    probe_engine = engine_for(source)
                    health = probes(source, probe_engine, vault)
                    assert all(
                        health["checks"][name]
                        for name in ("database", "worker", "ocr", "backup", "queue")
                    )
                    print("operational probes", health)
                    probe_engine.dispose()
                    started = time.perf_counter()
                    count = restore(
                        restored,
                        archive,
                        keyfile,
                        restored.storage_root,
                        digest(archive),
                    )
                    restore_seconds = time.perf_counter() - started
                    print(
                        "recovery drill files, ciphertext_bytes, backup_s, restore_s:",
                        count,
                        archive.stat().st_size,
                        round(backup_seconds, 3),
                        round(restore_seconds, 3),
                    )
                    assert count == 6 and restored.storage_root != source.storage_root
                    restored_app = create_app(restored)
                    for outsider in [False, True]:
                        with TestClient(
                            restored_app,
                            base_url="https://testserver",
                            headers={"X-VP-Request": "1"},
                        ) as client:
                            assert client.get("/api/v1/account").status_code == 401
                            assert client.post(
                                "/api/v1/login",
                                json={
                                    "workspace": workspace + ("2" if outsider else ""),
                                    "email": ("other" if outsider else "") + email,
                                    "password": password,
                                },
                            ).is_success

                            def local(endpoint):
                                return client.get(endpoint.replace(api, "/api/v1", 1))

                            if outsider:
                                assert all(
                                    local(endpoint).status_code == 404
                                    for endpoint in [
                                        exception_url,
                                        url,
                                        result_url,
                                        supplier_url,
                                    ]
                                )
                            else:
                                assert (
                                    local(url).content == pdf
                                    and local(supplier_url).json()["name"]
                                    == "Updated synthetic supplier"
                                )
                                assert (
                                    local(url + "/processing/" + job).json()[
                                        "classification"
                                    ]["category"]
                                    == "insurance"
                                )
                                assert (
                                    local(exception_url).json()["history"] == history
                                    and len(local(exception_url).json()["drafts"]) == 2
                                )
                                assert local(result_url).json()["id"] == run_id
                    restored_app.state.engine.dispose()
                page.goto(supplier_page)
                viewer.close()
                stop(api_proc)
                api_proc = server()
                stop(web)
                web = start(
                    ["node", "node_modules/vite/bin/vite.js", "--port", "55173"],
                    backend.parent / "frontend",
                    env,
                    front,
                )
                page.reload()
                persisted = page.request.get(exception_url).json()
                assert persisted["history"] == history and len(persisted["drafts"]) == 2
                assert (
                    persisted["run_id"] == run_id
                    and persisted["comparison"]["compared_run"] != run_id
                )
                assert persisted["outcome"] == "conflict"
                assert any(
                    f["status"] == "dismissed"
                    for f in page.request.get(result_url).json()["findings"]
                )
                expect(
                    page.get_by_role("heading", name="Updated synthetic supplier")
                ).to_be_visible()
                assert page.request.get(url).body() == pdf
                cited_doc = conflict["evidence"][source_index]["document"]
                assert page.request.delete(
                    supplier_url + "/documents/" + cited_doc,
                    headers={"X-VP-Request": "1"},
                ).ok
                assert page.request.get(source_url).status == 404
                historical = page.request.get(result_url).json()
                assert all(
                    "original" not in ref
                    for f in historical["findings"]
                    for ref in f["evidence"]
                    if ref["document"] == cited_doc
                )
                page.get_by_role("button", name="Sign out").click()
                expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
                assert page.request.get(supplier_url).status == 401
                browser.close()
        finally:
            stop(web)
    finally:
        stop(api_proc)

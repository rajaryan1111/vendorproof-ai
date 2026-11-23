"""Live local acceptance. Requires Chrome, npm ci, and a migrated disposable DB."""

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from app.config import Settings
from app.db import engine_for
from app.provision import provision
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


def test_browser_workflow(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    front = "http://localhost:55173"
    api = "http://localhost:58001/api/v1"
    env = {
        **os.environ,
        "VP_DATABASE_URL": os.environ["VP_TEST_DATABASE_URL"],
        "VP_COOKIE_SECURE": "false",
        "VP_STORAGE_ROOT": str(tmp_path),
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
                page = browser.new_page()
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
                source_url = verify + "/findings/" + conflict["id"] + "/sources/0"
                assert (
                    page.request.get(source_url).json()["excerpt"]
                    == conflict["evidence"][0]["original"]
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
                viewer = browser.new_context()
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
                assert any(
                    f["status"] == "dismissed"
                    for f in page.request.get(result_url).json()["findings"]
                )
                expect(
                    page.get_by_role("heading", name="Updated synthetic supplier")
                ).to_be_visible()
                assert page.request.get(url).body() == pdf
                cited_doc = conflict["evidence"][0]["document"]
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

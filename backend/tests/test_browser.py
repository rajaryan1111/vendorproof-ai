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
from test_workspace import sample_pdf

from app.config import Settings
from app.db import engine_for
from app.provision import provision


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
                pdf = sample_pdf()
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
                supplier_url = url.split("/documents/")[0]
                assert other.request.get(supplier_url).status == 404
                stop(api_proc)
                api_proc = server()
                page.reload()
                expect(
                    page.get_by_role("heading", name="Updated synthetic supplier")
                ).to_be_visible()
                assert page.request.get(url).body() == pdf
                page.get_by_role("button", name="Sign out").click()
                expect(page.get_by_role("heading", name="Sign in")).to_be_visible()
                assert page.request.get(supplier_url).status == 401
                browser.close()
        finally:
            stop(web)
    finally:
        stop(api_proc)

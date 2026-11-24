"""Local PostgreSQL-backed worker: python -m app.intelligence.worker [--once]."""

import argparse
import json
import os
import signal
import subprocess
import threading
import time
from uuid import UUID

from sqlalchemy import text

from ..config import Settings
from ..db import engine_for, query
from ..documents import PrivateFiles
from .child import command
from .schema import ENGINE, SCHEMA, Report

ERRORS = {
    "ocr_language_invalid",
    "ocr_unavailable",
    "ocr_timeout",
    "ocr_failed",
    "unsupported_pdf",
    "text_limit",
    "pdf_read_failed",
    "version_mismatch",
}


def execute(job, settings):
    path = PrivateFiles(settings.storage_root).path(
        job.organization_id, job.document_id
    )
    with (
        path.open("rb") as stream,
        subprocess.Popen(
            command(
                "app.intelligence.runner",
                settings,
                str(job.document_id),
                job.digest,
                settings.ocr_language,
            ),
            stdin=stream,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={
                key: os.environ[key]
                for key in ("PATH", "LANG", "TESSDATA_PREFIX")
                if key in os.environ
            },
        ) as proc,
    ):
        try:
            output, _ = proc.communicate(timeout=100)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            return None, "processing_timeout"
    if proc.returncode or len(output) > 16 * 1024 * 1024:
        return None, "processor_failed"
    payload = json.loads(output)
    if not isinstance(payload, dict) or b"\\u0000" in output:
        return None, "invalid_output"
    if payload.get("error") in ERRORS:
        return None, payload["error"]
    report = Report.model_validate_json(output)
    if report.document_id != job.document_id or report.version_digest != job.digest:
        return None, "version_mismatch"
    return report.model_dump_json(), None


def run_one(engine, settings, job_id=None):
    with engine.begin() as conn:
        conn.execute(
            text("""UPDATE processing_attempts SET state='failed',error_code='worker_interrupted',finished_at=now()
        WHERE state='processing' AND started_at<now()-interval '3 minutes'""")
        )
        job = query(
            conn,
            """SELECT j.*,d.digest,d.scanned_digest,d.archived OR s.archived AS archived FROM processing_attempts j JOIN documents d ON d.id=j.document_id AND d.organization_id=j.organization_id
        JOIN suppliers s ON s.id=j.supplier_id AND s.organization_id=j.organization_id
        WHERE j.state='queued' AND j.available_at<=now() AND j.implementation=:engine AND j.schema_version=:schema AND (CAST(:jid AS uuid) IS NULL OR j.id=:jid)
        ORDER BY j.created_at LIMIT 1 FOR UPDATE OF j SKIP LOCKED""",
            jid=job_id,
            engine=ENGINE,
            schema=SCHEMA,
        ).first()
        if not job:
            return False
        query(
            conn,
            "UPDATE processing_attempts SET state='processing',started_at=now() WHERE id=:id",
            id=job.id,
        )
    try:
        if job.archived:
            report, error = None, "archived"
        elif settings.environment == "production" and job.scanned_digest != job.digest:
            report, error = None, "scan_required"
        else:
            report, error = execute(job, settings)
    except (OSError, ValueError, TypeError):
        report, error = None, "processor_failed"
    with engine.begin() as conn:
        query(
            conn,
            """UPDATE processing_attempts SET state=:state,report=CAST(:report AS jsonb),error_code=:error,finished_at=now() WHERE id=:id AND state='processing'""",
            id=job.id,
            state="failed" if error else "needs_review",
            report=report,
            error=error,
        )
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--job", type=UUID)
    args = parser.parse_args()
    settings = Settings()
    engine = engine_for(settings)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    next_heartbeat = 0.0
    while not stopped.is_set():
        if time.monotonic() >= next_heartbeat:
            try:
                langs = (
                    subprocess.run(
                        ["tesseract", "--list-langs"],
                        capture_output=True,
                        timeout=5,
                        check=True,
                    )
                    .stdout.decode()
                    .splitlines()
                )
            except (OSError, subprocess.SubprocessError):
                langs = []
            with engine.begin() as conn:
                query(
                    conn,
                    "INSERT INTO worker_health VALUES(true,now(),:ocr) ON CONFLICT(singleton) DO UPDATE SET seen_at=excluded.seen_at,ocr_ready=excluded.ocr_ready",
                    ocr=settings.ocr_language in langs,
                )
            next_heartbeat = time.monotonic() + 20
        worked = run_one(engine, settings, args.job)
        if args.once or args.job:
            break
        if not worked:
            stopped.wait(1)

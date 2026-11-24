"""Host-local probes and retention inventory. Output contains aggregated counts only."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from .config import Settings
from .db import engine_for, query


def probes(settings, engine, backup_dir, backup_hours=26):
    with engine.connect() as conn:
        state = query(
            conn,
            """SELECT
        (SELECT seen_at>now()-interval '3 minutes' FROM worker_health) AS worker,
        (SELECT ocr_ready FROM worker_health) AS ocr,
        count(*) FILTER(WHERE state='queued') AS queued,
        COALESCE(EXTRACT(EPOCH FROM now()-min(available_at) FILTER(WHERE state='queued' AND available_at<=now())),0)::int AS oldest_seconds,
        count(*) FILTER(WHERE state='failed' AND finished_at>now()-interval '15 minutes') AS recent_failures,
        count(*) FILTER(WHERE state='failed' AND error_code LIKE 'ocr_%' AND finished_at>now()-interval '15 minutes') AS ocr_failures,
        avg(EXTRACT(EPOCH FROM finished_at-started_at)) FILTER(WHERE finished_at>now()-interval '15 minutes')::float AS mean_job_seconds
        FROM processing_attempts""",
        ).one()
    disk = shutil.disk_usage(settings.storage_root)
    backups = [
        p.stat().st_mtime for p in backup_dir.glob("vendorproof-*.age") if p.is_file()
    ]
    checks = {
        "database": True,
        "worker": bool(state.worker),
        "ocr": bool(state.ocr),
        "queue": state.oldest_seconds <= 600 and state.recent_failures < 3,
        "storage": disk.free / disk.total >= 0.15,
        "backup": bool(backups and time.time() - max(backups) < 3600 * backup_hours),
    }
    if settings.scanner_socket:
        from .safety import scan

        try:
            checks["scanner"] = scan(b"VendorProof readiness", settings)
        except Exception:  # noqa: BLE001 - emit only a redacted health status.
            checks["scanner"] = False
    return {
        "checks": checks,
        "queued": state.queued,
        "oldest_seconds": state.oldest_seconds,
        "recent_failures": state.recent_failures,
        "ocr_failures": state.ocr_failures,
        "mean_job_seconds": state.mean_job_seconds,
    }


def retention_inventory(conn, tenant):
    tables = (
        "memberships",
        "member_access_events",
        "suppliers",
        "documents",
        "processing_attempts",
        "verification_policies",
        "verification_runs",
        "verification_findings",
        "verification_reviews",
        "exception_drafts",
        "exception_corrections",
        "activity",
    )
    if not query(
        conn, "SELECT id FROM organizations WHERE id=:org", org=tenant
    ).first():
        raise ValueError("Unknown workspace")
    return {
        table: conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE organization_id=:tenant"),
            {"tenant": tenant},
        ).scalar_one()
        for table in tables
    }


def scan_backlog(settings, engine):
    from .safety import scan

    with engine.begin() as conn:
        rows = query(
            conn,
            "SELECT id,organization_id,digest FROM documents WHERE scanned_digest IS NULL ORDER BY id LIMIT 20 FOR UPDATE SKIP LOCKED",
        ).all()
        for row in rows:
            with (settings.storage_root / str(row.organization_id) / str(row.id)).open(
                "rb"
            ) as stream:
                data = stream.read(5 * 1024**2 + 1)
            if (
                len(data) > 5 * 1024**2
                or hashlib.sha256(data).hexdigest() != row.digest
                or not scan(data, settings)
            ):
                raise ValueError("Legacy object requires investigation")
            query(
                conn,
                "UPDATE documents SET scanned_digest=digest WHERE id=:id",
                id=row.id,
            )
        return len(rows)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("monitor").add_argument("--backups", type=Path, required=True)
    sub.add_parser("retention-inventory").add_argument("tenant", type=UUID)
    sub.add_parser("preflight")
    sub.add_parser("scan-backlog")
    args = parser.parse_args()
    settings = Settings()
    engine = engine_for(settings)
    try:
        if args.action == "preflight":
            from .intelligence.child import command
            from .safety import scan

            if (
                settings.environment != "production"
                or os.geteuid() == 0
                or not scan(b"VendorProof readiness", settings)
            ):
                raise ValueError("Production prerequisites unavailable")
            result = subprocess.run(
                command("app.intelligence.probe", settings),
                capture_output=True,
                check=True,
                timeout=15,
                env={"PATH": os.defpath},
            )
            if result.stdout.strip() != b"parser-ready":
                raise ValueError("Parser readiness failed")
            with engine.connect() as conn:
                if (
                    conn.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()
                    != "006_member_access"
                ):
                    raise ValueError("Migration required")
            print(json.dumps({"operation": "preflight", "outcome": "ready"}))
            return 0
        if args.action == "scan-backlog":
            print(json.dumps({"scanned": scan_backlog(settings, engine)}))
            return 0
        if args.action == "monitor":
            result = probes(settings, engine, args.backups)
            print(json.dumps(result))
            return 0 if all(result["checks"].values()) else 1
        with engine.connect() as conn:
            print(json.dumps(retention_inventory(conn, args.tenant)))
    except Exception:  # noqa: BLE001 - no database, path or scanner diagnostics in monitoring.
        print(json.dumps({"operation": args.action, "outcome": "unavailable"}))
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

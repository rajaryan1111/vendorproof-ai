"""Encrypted, coordinated DB/object backup and restore into empty destinations."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from sqlalchemy.engine import make_url

from .config import Settings


def db_params(settings):
    url = make_url(str(settings.database_url))
    return {
        k: v
        for k, v in {
            "dbname": url.database,
            "host": url.host,
            "port": url.port,
            "user": url.username,
            "password": url.password,
            **url.query,
        }.items()
        if v is not None
    }


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def inventory(conn):
    return {
        f"{org}/{doc}": sha
        for org, doc, sha in conn.execute(
            "SELECT organization_id,id,digest FROM documents"
        )
    }


def backup(settings, dest, recipient, days):
    if not 1 <= days <= 3650 or not recipient.startswith("age1"):
        raise ValueError("Set a backup recipient and retention days")
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    if dest.stat().st_mode & 0o077:
        raise ValueError("Backup directory must be private")
    params = db_params(settings)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    name = f"vendorproof-{stamp}-{uuid4().hex}.age"
    with (
        tempfile.TemporaryDirectory() as stage,
        tempfile.TemporaryDirectory(dir=dest) as sealed,
    ):
        stage = Path(stage)
        with psycopg.connect(**params) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
            files = inventory(conn)
            subprocess.run(
                [
                    "pg_dump",
                    "-Fc",
                    "--dbname",
                    params["dbname"],
                    "--no-owner",
                    "--no-acl",
                    "--exclude-table-data=sessions",
                    "--exclude-table-data=login_limits",
                    "--exclude-table-data=worker_health",
                    "--snapshot",
                    snapshot,
                    "-f",
                    str(stage / "database.dump"),
                ],
                env=restore_env(params),
                check=True,
            )
        with tarfile.open(stage / "bundle", "w") as bundle:
            bundle.add(stage / "database.dump", arcname="database.dump")
            for key, sha in files.items():
                path = settings.storage_root / key
                if digest(path) != sha:
                    raise ValueError("Private object failed integrity check")
                bundle.add(path, arcname="objects/" + key, recursive=False)
        subprocess.run(
            [
                "age",
                "-r",
                recipient,
                "-o",
                str(Path(sealed) / "encrypted"),
                str(stage / "bundle"),
            ],
            check=True,
        )
        os.chmod(Path(sealed) / "encrypted", 0o600)
        os.replace(Path(sealed) / "encrypted", dest / name)
    cutoff = time.time() - days * 86400
    for old in dest.glob("vendorproof-*.age"):
        if (
            re.fullmatch(r"vendorproof-\d{8}T\d{6}Z-[a-f0-9]{32}\.age", old.name)
            and old != dest / name
            and old.stat().st_mtime < cutoff
        ):
            old.unlink()
    return dest / name


def restore(settings, archive, identity, root, expected_digest):
    if (
        not re.fullmatch(r"[a-f0-9]{64}", expected_digest)
        or digest(archive) != expected_digest
    ):
        raise ValueError("Archive digest differs from recovery inventory")
    params = db_params(settings)
    if root.exists():
        raise ValueError("Restore requires a new object directory")
    with psycopg.connect(**params) as conn:
        if conn.execute(
            "SELECT EXISTS(SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname!='information_schema' AND c.relkind IN ('r','p','v','S'))"
        ).fetchone()[0]:
            raise ValueError("Restore requires an empty database")
    with tempfile.TemporaryDirectory(dir=root.parent) as stage:
        stage = Path(stage)
        subprocess.run(
            [
                "age",
                "-d",
                "-i",
                str(identity),
                "-o",
                str(stage / "bundle"),
                str(archive),
            ],
            check=True,
        )
        objects = stage / "objects"
        objects.mkdir(mode=0o700)
        with tarfile.open(stage / "bundle", "r:") as bundle:
            for entry in bundle:
                parts = entry.name.split("/")
                if not entry.isfile() or not (
                    parts == ["database.dump"]
                    or len(parts) == 3
                    and parts[0] == "objects"
                    and all(str(UUID(x)) == x for x in parts[1:])
                ):
                    raise ValueError("Invalid recovery archive member")
                path = stage / entry.name
                path.parent.mkdir(mode=0o700, exist_ok=True)
                with path.open("xb") as out:
                    shutil.copyfileobj(bundle.extractfile(entry), out)
                path.chmod(0o600)
        subprocess.run(
            [
                "pg_restore",
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                "--dbname",
                params["dbname"],
                str(stage / "database.dump"),
            ],
            env=restore_env(params),
            check=True,
        )
        with psycopg.connect(**params) as conn:
            files = inventory(conn)
            if len(files) != sum(1 for p in objects.glob("*/*") if p.is_file()) or any(
                digest(objects / key) != sha for key, sha in files.items()
            ):
                raise ValueError("Restored DB and private objects disagree")
        objects.rename(root)
    return len(files)


def restore_env(params):
    keys = {
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "host": "PGHOST",
        "port": "PGPORT",
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
    }
    return {
        **os.environ,
        **{env: str(params[k]) for k, env in keys.items() if k in params},
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--destination", required=True, type=Path)
    b.add_argument("--recipient", required=True)
    b.add_argument("--days", required=True, type=int)
    r = sub.add_parser("restore")
    for opt in ("archive", "identity", "objects"):
        r.add_argument("--" + opt, type=Path, required=True)
    r.add_argument("--sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.action == "backup":
        archive = backup(Settings(), args.destination, args.recipient, args.days)
        print(
            json.dumps(
                {"event": "snapshot", "name": archive.name, "sha256": digest(archive)}
            )
        )
    else:
        restore(Settings(), args.archive, args.identity, args.objects, args.sha256)
    print(json.dumps({"event": args.action, "outcome": "success"}))


if __name__ == "__main__":
    main()

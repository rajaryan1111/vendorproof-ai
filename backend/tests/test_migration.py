import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import DBAPIError


def test_migrate_empty_schema(monkeypatch):
    url = os.environ["VP_TEST_DATABASE_URL"]
    schema = "vp_test_" + uuid4().hex
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    monkeypatch.setenv("VP_DATABASE_URL", url)
    monkeypatch.setenv("PGOPTIONS", "-c search_path=" + schema)
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "001_workspace")
        isolated = create_engine(url)
        with isolated.begin() as conn:
            org = conn.exec_driver_sql(
                "INSERT INTO organizations(name) VALUES('Synthetic migration') RETURNING id"
            ).scalar_one()
            supplier = conn.exec_driver_sql(
                "INSERT INTO suppliers(organization_id,name) VALUES(%s,'Synthetic') RETURNING id",
                (org,),
            ).scalar_one()
            doc = uuid4()
            conn.exec_driver_sql(
                "INSERT INTO documents(id,organization_id,supplier_id,filename,bytes,digest) VALUES(%s,%s,%s,'synthetic.pdf',1,'fixture')",
                (doc, org, supplier),
            )
        command.upgrade(config, "002_processing")
        with isolated.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO processing_attempts(organization_id,supplier_id,document_id,attempt,implementation,schema_version) VALUES(%s,%s,%s,1,'local/1','fields/1')",
                (org, supplier, doc),
            )
        command.upgrade(config, "003_verification")
        with isolated.begin() as conn:
            actor = conn.exec_driver_sql(
                "INSERT INTO users(email,password_hash) VALUES('migration@example.invalid','fixture') RETURNING id"
            ).scalar_one()
            conn.exec_driver_sql(
                "INSERT INTO memberships(user_id,organization_id,role) VALUES(%s,%s,'reviewer')",
                (actor, org),
            )
            conn.exec_driver_sql(
                "INSERT INTO verification_policies(organization_id,supplier_id,version,body,actor) VALUES(%s,%s,1,'{}',%s)",
                (org, supplier, actor),
            )
            rid = conn.exec_driver_sql(
                "INSERT INTO verification_runs(organization_id,supplier_id,policy_version,rule_version,as_of,fingerprint,inventory,checklist,actor) VALUES(%s,%s,1,'fixture',current_date,'fixture','[]','[]',%s) RETURNING id",
                (org, supplier, actor),
            ).scalar_one()
            fid = conn.exec_driver_sql(
                "INSERT INTO verification_findings(organization_id,supplier_id,run_id,rule,outcome,severity,explanation,quality,requires_review,evidence) VALUES(%s,%s,%s,'requirement','missing_document','medium','agreement: missing','inventory',true,'[]') RETURNING id",
                (org, supplier, rid),
            ).scalar_one()
            seq = conn.exec_driver_sql(
                "INSERT INTO verification_reviews(organization_id,supplier_id,finding_id,actor,status,reason) VALUES(%s,%s,%s,%s,'clarification_requested','Synthetic clarification') RETURNING seq",
                (org, supplier, fid, actor),
            ).scalar_one()
        command.upgrade(config, "head")
        with isolated.begin() as conn:
            assert conn.exec_driver_sql(
                "SELECT status,revision FROM exception_queue WHERE id=%s", (fid,)
            ).one() == ("awaiting_supplier_response", seq)
            assert conn.exec_driver_sql(
                "SELECT active FROM memberships WHERE user_id=%s", (actor,)
            ).scalar_one()
            conn.exec_driver_sql(
                "UPDATE memberships SET active=false WHERE user_id=%s", (actor,)
            )
        with pytest.raises(DBAPIError, match="archival plan"):
            command.downgrade(config, "003_verification")
        with isolated.begin() as conn:
            conn.exec_driver_sql(
                "UPDATE memberships SET active=true WHERE user_id=%s", (actor,)
            )
            assert conn.exec_driver_sql(
                "SELECT status,reason FROM verification_reviews WHERE seq=%s", (seq,)
            ).one() == ("clarification_requested", "Synthetic clarification")
        with isolated.begin() as conn:
            assert (
                conn.exec_driver_sql(
                    "SELECT filename FROM documents WHERE id=%s", (doc,)
                ).scalar_one()
                == "synthetic.pdf"
            )
            assert (
                conn.exec_driver_sql(
                    "SELECT count(*) FROM processing_attempts"
                ).scalar_one()
                == 1
            )
        isolated.dispose()
        assert set(inspect(engine).get_table_names(schema=schema)) == {
            "organizations",
            "users",
            "memberships",
            "member_access_events",
            "sessions",
            "suppliers",
            "documents",
            "verification_policies",
            "verification_runs",
            "verification_findings",
            "verification_reviews",
            "exception_corrections",
            "exception_drafts",
            "worker_health",
            "processing_attempts",
            "activity",
            "login_limits",
            "alembic_version",
        }
        command.downgrade(config, "base")
        assert inspect(engine).get_table_names(schema=schema) == ["alembic_version"]
    finally:
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        engine.dispose()

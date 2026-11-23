import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
        command.upgrade(config, "head")
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
            "sessions",
            "suppliers",
            "documents",
            "verification_policies",
            "verification_runs",
            "verification_findings",
            "verification_reviews",
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

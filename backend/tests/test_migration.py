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
        command.upgrade(config, "head")
        assert set(inspect(engine).get_table_names(schema=schema)) == {
            "organizations",
            "users",
            "memberships",
            "sessions",
            "suppliers",
            "documents",
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

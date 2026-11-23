from fastapi import HTTPException, Request
from sqlalchemy import create_engine, text


def engine_for(settings):
    if not settings.database_url:
        raise RuntimeError("Set VP_DATABASE_URL")
    return create_engine(
        str(settings.database_url), pool_pre_ping=True, hide_parameters=True
    )


def db(request: Request):
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503)
    with engine.begin() as connection:
        yield connection


def query(connection, sql, **params):
    return connection.execute(text(sql), params).mappings()

from fastapi import HTTPException, Request
from sqlalchemy import create_engine, text


def engine_for(settings):
    if not settings.database_url:
        raise RuntimeError("Set VP_DATABASE_URL")
    return create_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        hide_parameters=True,
        pool_size=4,
        max_overflow=2,
        pool_timeout=5,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=30000 -c lock_timeout=5000",
        }
        if settings.environment == "production"
        else {"connect_timeout": 5},
    )


def db(request: Request):
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503)
    with engine.begin() as connection:
        yield connection


def query(connection, sql, **params):
    return connection.execute(text(sql), params).mappings()

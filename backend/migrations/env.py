from alembic import context
from app.config import Settings
from app.db import engine_for

with engine_for(Settings()).begin() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()

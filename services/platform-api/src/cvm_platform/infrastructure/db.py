from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from cvm_platform.settings.config import settings


Base = declarative_base()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def initialize_database() -> None:
    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "Only PostgreSQL is supported. Set CVM_DATABASE_URL to a postgresql+psycopg connection string."
        )
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_lock(871245019533682001)"))
        try:
            Base.metadata.create_all(bind=connection)
            connection.execute(text("ALTER TABLE search_run ADD COLUMN IF NOT EXISTS workflow_id VARCHAR(128)"))
            connection.execute(text("ALTER TABLE search_run ADD COLUMN IF NOT EXISTS temporal_namespace VARCHAR(64)"))
            connection.execute(text("ALTER TABLE search_run ADD COLUMN IF NOT EXISTS temporal_task_queue VARCHAR(128)"))
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(871245019533682001)"))


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

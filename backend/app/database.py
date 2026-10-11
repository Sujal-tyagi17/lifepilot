"""Database setup using SQLAlchemy. Defaults to a local SQLite file (zero setup)."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.config import settings

db_url = settings.database_url
# Fix legacy or hosted postgres:// scheme (Supabase, Neon, Render, Heroku) for SQLAlchemy
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and "+psycopg" not in db_url and "+psycopg2" not in db_url and "+asyncpg" not in db_url:
    # Default to psycopg v3 driver if not explicitly specified
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {}
engine_kwargs = {
    "future": True,
    "pool_pre_ping": True,
}

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # PostgreSQL connection pooling settings
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 1800,
    })

engine = create_engine(db_url, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import models so they register with Base before create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Safe schema migration for existing PostgreSQL / SQLite tables
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE profiles ADD COLUMN user_id VARCHAR(120);",
        "ALTER TABLE match_results ADD COLUMN description TEXT;",
        "ALTER TABLE match_results ADD COLUMN criteria JSON;",
        "ALTER TABLE match_results ALTER COLUMN opportunity_id TYPE VARCHAR(400);",
        "ALTER TABLE match_results ALTER COLUMN title TYPE VARCHAR(400);",
        "ALTER TABLE match_results ALTER COLUMN provider TYPE VARCHAR(400);",
        "ALTER TABLE match_results ALTER COLUMN url TYPE VARCHAR(1000);",
        "ALTER TABLE match_results ALTER COLUMN amount TYPE VARCHAR(300);",
        "ALTER TABLE match_results ADD COLUMN status VARCHAR(20);",
        "ALTER TABLE match_results ADD COLUMN notes JSON;",
        "ALTER TABLE match_results ADD COLUMN deadline_note VARCHAR(200);",
        "ALTER TABLE profiles ADD COLUMN guest_key VARCHAR(64);",
    ]
    for stmt in migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass

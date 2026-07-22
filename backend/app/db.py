"""Database engine/session wiring.

Portable across SQLite (local/dev, default) and PostgreSQL (production via
DATABASE_URL). Only account/billing/job metadata is ever stored here — never
uploaded file contents.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./pdf2word.db")
# Render/Heroku sometimes provide a "postgres://" URL; SQLAlchemy needs "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False for FastAPI's threaded workers.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

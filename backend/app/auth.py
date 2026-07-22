"""Magic-link + session primitives.

Tokens are random and stored only as SHA-256 hashes; the raw token exists just
long enough to email it (magic link) or set it in a cookie (session).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.config import MAGIC_LINK_TTL_MINUTES, SESSION_COOKIE, SESSION_TTL_DAYS
from app.db import get_db
from app.models import MagicLink, Session, User


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    # SQLite may hand back naive datetimes; treat stored times as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- magic links ---

def create_magic_link(db: OrmSession, email: str) -> str:
    """Create a single-use magic-link token; returns the RAW token."""
    token = secrets.token_urlsafe(32)
    link = MagicLink(
        email=email.lower(),
        token_hash=_hash(token),
        expires_at=_now() + timedelta(minutes=MAGIC_LINK_TTL_MINUTES),
    )
    db.add(link)
    db.commit()
    return token


def consume_magic_link(db: OrmSession, token: str) -> str | None:
    """Validate + burn a magic link. Returns the email on success, else None."""
    row = db.scalar(select(MagicLink).where(MagicLink.token_hash == _hash(token)))
    if row is None or row.consumed_at is not None:
        return None
    if _aware(row.expires_at) < _now():
        return None
    row.consumed_at = _now()
    db.commit()
    return row.email


# --- users + sessions ---

def get_or_create_user(db: OrmSession, email: str) -> User:
    email = email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        db.add(user)
        db.commit()
    return user


def create_session(db: OrmSession, user: User) -> str:
    """Create a session; returns the RAW session token for the cookie."""
    token = secrets.token_urlsafe(32)
    sess = Session(
        token_hash=_hash(token),
        user_id=user.id,
        expires_at=_now() + timedelta(days=SESSION_TTL_DAYS),
    )
    db.add(sess)
    db.commit()
    return token


def destroy_session(db: OrmSession, token: str) -> None:
    row = db.scalar(select(Session).where(Session.token_hash == _hash(token)))
    if row is not None:
        db.delete(row)
        db.commit()


def user_for_token(db: OrmSession, token: str | None) -> User | None:
    """Resolve a raw session token to a User (or None). Used by the dependency
    and by non-dependency call sites (e.g. the rate-limit exemption)."""
    if not token:
        return None
    row = db.scalar(select(Session).where(Session.token_hash == _hash(token)))
    if row is None or _aware(row.expires_at) < _now():
        return None
    return row.user


def get_current_user(request: Request, db: OrmSession = Depends(get_db)) -> User | None:
    """Dependency: resolve the session cookie to a User, or None if anonymous."""
    return user_for_token(db, request.cookies.get(SESSION_COOKIE))

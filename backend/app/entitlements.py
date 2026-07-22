"""Central entitlement resolver — the single source of truth for limits.

Anonymous or free users get FREE; a user with an active/trialing subscription
whose period hasn't ended gets PRO. Endpoints call resolve() rather than
hardcoding limits, so pricing changes live in one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app import config
from app.models import Subscription, User

_ACTIVE_STATUSES = {"active", "trialing"}


@dataclass(frozen=True)
class Limits:
    tier: str
    max_file_size_bytes: int
    max_pages: int
    max_ocr_pages: int
    max_batch_files: int          # 1 == no batch
    rate_limit: str | None        # None == no hourly cap


FREE = Limits(
    tier="free",
    max_file_size_bytes=config.MAX_FILE_SIZE_BYTES,
    max_pages=config.MAX_PAGES,
    max_ocr_pages=config.MAX_OCR_PAGES,
    max_batch_files=1,
    rate_limit=config.RATE_LIMIT,
)

PRO = Limits(
    tier="pro",
    max_file_size_bytes=config.PRO_MAX_FILE_SIZE_BYTES,
    max_pages=config.PRO_MAX_PAGES,
    max_ocr_pages=config.PRO_MAX_OCR_PAGES,
    max_batch_files=config.PRO_MAX_BATCH_FILES,
    rate_limit=None,
)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def active_subscription(db: OrmSession, user: User) -> Subscription | None:
    now = datetime.now(timezone.utc)
    subs = db.scalars(
        select(Subscription).where(Subscription.user_id == user.id)
    ).all()
    for s in subs:
        if s.status in _ACTIVE_STATUSES and _aware(s.current_period_end) > now:
            return s
    return None


def resolve(db: OrmSession, user: User | None) -> Limits:
    if user is None:
        return FREE
    return PRO if active_subscription(db, user) is not None else FREE

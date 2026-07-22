"""Tiny per-IP fixed-window throttle for auth endpoints.

Independent of the slowapi limiter used by /api/convert. In-memory and
single-instance; for multi-instance production move this to Redis or a DB
counter. Kept separate so it never interferes with conversion rate limiting.
"""
from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request

_WINDOW_SECONDS = 3600
_lock = threading.Lock()
_hits: dict[tuple[str, str], list[float]] = {}


def throttle(request: Request, max_per_hour: int) -> None:
    ip = request.client.host if request.client else "unknown"
    key = (request.url.path, ip)
    now = time.time()
    with _lock:
        recent = [t for t in _hits.get(key, []) if now - t < _WINDOW_SECONDS]
        if len(recent) >= max_per_hour:
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED",
                        "message": "Too many requests — try again later."},
            )
        recent.append(now)
        _hits[key] = recent

"""Auth HTTP endpoints: request-link, verify, logout, me."""
from __future__ import annotations

from email_validator import EmailNotValidError, validate_email
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session as OrmSession

from app.auth import (
    consume_magic_link,
    create_magic_link,
    create_session,
    destroy_session,
    get_current_user,
    get_or_create_user,
)
from app.config import (
    APP_BASE_URL,
    API_BASE_URL,
    AUTH_REQUEST_MAX_PER_HOUR,
    COOKIE_SECURE,
    SESSION_COOKIE,
    SESSION_COOKIE_SAMESITE,
    SESSION_TTL_DAYS,
)
from app.db import get_db
from app.emailer import send_magic_link
from app.ratelimit import throttle
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/request-link")
def request_link(request: Request, payload: dict, db: OrmSession = Depends(get_db)):
    """Email a sign-in link. Always 200 — never reveal whether an email exists."""
    throttle(request, AUTH_REQUEST_MAX_PER_HOUR)
    raw = (payload or {}).get("email", "")
    try:
        email = validate_email(raw, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        # Still return 200 to avoid leaking validity / enabling enumeration.
        return {"ok": True}
    token = create_magic_link(db, email)
    link = f"{API_BASE_URL}/api/auth/verify?token={token}"
    try:
        send_magic_link(email, link)
    except Exception:
        # Don't leak send failures to the client; log server-side in real deploy.
        pass
    return {"ok": True}


@router.get("/verify")
def verify(request: Request, token: str, db: OrmSession = Depends(get_db)):
    """Consume a magic link, open a session, set cookie, redirect to the app."""
    email = consume_magic_link(db, token)
    if email is None:
        return JSONResponse(
            status_code=400,
            content={"code": "BAD_LINK", "message": "This sign-in link is invalid or expired."},
        )
    user = get_or_create_user(db, email)
    session_token = create_session(db, user)
    resp = RedirectResponse(url=APP_BASE_URL, status_code=303)
    # SameSite=None requires Secure; enforce it so the cookie isn't silently dropped.
    secure = COOKIE_SECURE or SESSION_COOKIE_SAMESITE == "none"
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=SESSION_TTL_DAYS * 86400,
        httponly=True,
        secure=secure,
        samesite=SESSION_COOKIE_SAMESITE,
        path="/",
    )
    return resp


@router.post("/logout")
def logout(request: Request, db: OrmSession = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        destroy_session(db, token)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/me")
def me(user: User | None = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    if user is None:
        return JSONResponse(status_code=401, content={"code": "ANON", "message": "Not signed in."})
    from app.entitlements import resolve
    return {"email": user.email, "id": user.id, "tier": resolve(db, user).tier}

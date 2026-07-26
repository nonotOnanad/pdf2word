"""Auth HTTP endpoints: request-link, verify, logout, me."""
from __future__ import annotations

import logging

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

logger = logging.getLogger("pdf2word.auth")

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
    except Exception as exc:
        # Never leak send failures to the client (account enumeration), but they
        # MUST be visible server-side or a misconfigured provider fails silently.
        logger.error("magic-link send failed: %s: %s", type(exc).__name__, exc)
    return {"ok": True}


def _stripe_status() -> dict:
    """Non-secret Stripe readiness: presence and shape only, never values.

    Catches the usual mistakes — missing vars, a key/price/secret pasted into
    the wrong field, or a truncated id — before a real checkout is attempted.
    """
    from app import config

    sk = config.STRIPE_SECRET_KEY
    whsec = config.STRIPE_WEBHOOK_SECRET
    monthly = config.STRIPE_PRICE_MONTHLY
    annual = config.STRIPE_PRICE_ANNUAL
    ready = all([
        sk.startswith("sk_"), whsec.startswith("whsec_"),
        monthly.startswith("price_"), annual.startswith("price_"),
    ])
    return {
        "stripe_secret_key_ok": sk.startswith("sk_"),
        "stripe_mode": ("test" if "_test_" in sk else "live") if sk else None,
        "stripe_webhook_secret_ok": whsec.startswith("whsec_"),
        "stripe_price_monthly_ok": monthly.startswith("price_"),
        "stripe_price_annual_ok": annual.startswith("price_"),
        "stripe_prices_distinct": bool(monthly and annual and monthly != annual),
        "billing_ready": ready,
    }


@router.get("/config-check")
def config_check():
    """Non-secret diagnostic: is email/auth configured? No values are exposed —
    only whether each setting is present and correctly shaped."""
    import os

    from app.config import APP_BASE_URL, COOKIE_SECURE, SESSION_COOKIE_SAMESITE

    api_base = API_BASE_URL
    key = os.environ.get("RESEND_API_KEY", "")
    sender = os.environ.get("EMAIL_FROM", "")
    # Cross-site cookies (frontend and API are different origins) require
    # SameSite=None AND Secure, or the browser silently drops the session.
    cookie_ok = SESSION_COOKIE_SAMESITE == "none" and COOKIE_SECURE
    return {
        "email_provider": os.environ.get("EMAIL_PROVIDER", "console"),
        "resend_api_key_set": bool(key),
        "resend_api_key_prefix_ok": key.startswith("re_") if key else False,
        "email_from_set": bool(sender),
        "email_from_domain": sender.split("@")[-1] if "@" in sender else None,
        "api_base_url": api_base,
        "api_base_url_is_localhost": "localhost" in api_base or "127.0.0.1" in api_base,
        # --- post-login redirect + session cookie ---
        "app_base_url": APP_BASE_URL,
        "app_base_url_is_localhost": "localhost" in APP_BASE_URL or "127.0.0.1" in APP_BASE_URL,
        "cookie_samesite": SESSION_COOKIE_SAMESITE,
        "cookie_secure": COOKIE_SECURE,
        "cross_site_cookie_ok": cookie_ok,
        # --- billing (Stripe) ---
        **_stripe_status(),
    }


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

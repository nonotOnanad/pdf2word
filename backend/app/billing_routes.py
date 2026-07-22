"""Billing endpoints: checkout, customer portal, Stripe webhook."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as OrmSession

from app.auth import get_current_user
from app.billing import (
    BillingError,
    apply_event,
    create_checkout_url,
    create_portal_url,
    parse_event,
)
from app.db import get_db
from app.models import User

router = APIRouter(tags=["billing"])


def _require_user(user: User | None):
    if user is None:
        return JSONResponse(status_code=401, content={"code": "ANON", "message": "Sign in first."})
    return None


@router.post("/api/billing/checkout")
def checkout(payload: dict, user: User | None = Depends(get_current_user),
             db: OrmSession = Depends(get_db)):
    guard = _require_user(user)
    if guard:
        return guard
    plan = (payload or {}).get("plan", "monthly")
    try:
        url = create_checkout_url(db, user, plan)
    except BillingError as exc:
        return JSONResponse(status_code=503, content={"code": "BILLING_UNAVAILABLE", "message": str(exc)})
    return {"url": url}


@router.post("/api/billing/portal")
def portal(user: User | None = Depends(get_current_user), db: OrmSession = Depends(get_db)):
    guard = _require_user(user)
    if guard:
        return guard
    try:
        url = create_portal_url(db, user)
    except BillingError as exc:
        return JSONResponse(status_code=503, content={"code": "BILLING_UNAVAILABLE", "message": str(exc)})
    return {"url": url}


@router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request, db: OrmSession = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = parse_event(payload, sig)
    except Exception:
        # bad signature / malformed — reject so Stripe retries or you investigate
        return JSONResponse(status_code=400, content={"code": "BAD_SIGNATURE", "message": "Invalid signature."})
    apply_event(db, event)
    return {"received": True}

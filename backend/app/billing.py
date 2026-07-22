"""Stripe helpers: customer, checkout, portal, and webhook event application.

Design: we create the Stripe Customer at checkout time and store its id, so
every later subscription.* webhook maps back to a user via stripe_customer_id
with no extra API calls in the webhook path.
"""
from __future__ import annotations

from datetime import datetime, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app import config
from app.models import Subscription, User


class BillingError(Exception):
    pass


def _client() -> None:
    if not config.STRIPE_SECRET_KEY:
        raise BillingError("STRIPE_SECRET_KEY not set")
    stripe.api_key = config.STRIPE_SECRET_KEY


def _plan_for_price(price_id: str) -> str:
    if price_id and price_id == config.STRIPE_PRICE_MONTHLY:
        return "pro_monthly"
    if price_id and price_id == config.STRIPE_PRICE_ANNUAL:
        return "pro_annual"
    return "unknown"


def ensure_customer(db: OrmSession, user: User) -> str:
    """Return the user's Stripe customer id, creating it on first use."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    _client()
    customer = stripe.Customer.create(email=user.email, metadata={"user_id": user.id})
    user.stripe_customer_id = customer["id"]
    db.commit()
    return user.stripe_customer_id


def create_checkout_url(db: OrmSession, user: User, plan: str) -> str:
    price = config.STRIPE_PRICE_ANNUAL if plan == "annual" else config.STRIPE_PRICE_MONTHLY
    if not price:
        raise BillingError("price id not configured")
    customer_id = ensure_customer(db, user)
    _client()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=user.id,
        line_items=[{"price": price, "quantity": 1}],
        success_url=config.BILLING_SUCCESS_URL,
        cancel_url=config.BILLING_CANCEL_URL,
    )
    return session["url"]


def create_portal_url(db: OrmSession, user: User) -> str:
    if not user.stripe_customer_id:
        raise BillingError("no customer for user")
    _client()
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=config.APP_BASE_URL
    )
    return session["url"]


def parse_event(payload: bytes, sig_header: str) -> dict:
    """Verify the Stripe signature and return the event (raises on bad sig)."""
    if not config.STRIPE_WEBHOOK_SECRET:
        raise BillingError("STRIPE_WEBHOOK_SECRET not set")
    return stripe.Webhook.construct_event(
        payload, sig_header, config.STRIPE_WEBHOOK_SECRET
    )


def _get(obj, key, default=None):
    # Works for both plain dicts and Stripe objects (which lack .get()).
    return obj[key] if key in obj else default


def _upsert_subscription(db: OrmSession, sub_obj) -> None:
    customer_id = _get(sub_obj, "customer")
    if customer_id is None:
        return
    user = db.scalar(select(User).where(User.stripe_customer_id == customer_id))
    if user is None:
        return  # unknown customer; nothing to attach to
    price_id = None
    try:
        price_id = sub_obj["items"]["data"][0]["price"]["id"]
    except (KeyError, IndexError, TypeError):
        pass
    period_end = datetime.fromtimestamp(
        _get(sub_obj, "current_period_end", 0), tz=timezone.utc
    )
    sub_id = sub_obj["id"]
    status = _get(sub_obj, "status", "unknown")
    row = db.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
    )
    if row is None:
        row = Subscription(
            user_id=user.id,
            stripe_subscription_id=sub_id,
            status=status,
            plan=_plan_for_price(price_id),
            current_period_end=period_end,
        )
        db.add(row)
    else:
        row.status = status
        row.plan = _plan_for_price(price_id)
        row.current_period_end = period_end
    db.commit()


def apply_event(db: OrmSession, event: dict) -> None:
    """Apply a verified webhook event to local subscription state (idempotent)."""
    etype = _get(event, "type", "")
    data = _get(event, "data", {})
    obj = _get(data, "object", {})
    if etype.startswith("customer.subscription."):
        _upsert_subscription(db, obj)
    elif etype == "checkout.session.completed":
        # Customer/user link already exists (set at checkout); nothing required.
        # Subscription rows arrive via customer.subscription.* events.
        pass

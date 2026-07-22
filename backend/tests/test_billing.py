"""Stripe billing tests — Stripe API mocked; webhook signature is REAL.

The webhook path builds a genuine Stripe-signature header with a test secret,
so signature verification is actually exercised (not bypassed).
"""
import hashlib
import hmac
import importlib
import json
import time

import pytest
import stripe
from fastapi.testclient import TestClient

WEBHOOK_SECRET = "whsec_testsecret"


@pytest.fixture(autouse=True)
def stripe_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("STRIPE_PRICE_MONTHLY", "price_monthly")
    monkeypatch.setenv("STRIPE_PRICE_ANNUAL", "price_annual")
    import app.config
    importlib.reload(app.config)   # billing reads config.* dynamically
    yield


import app.main as main  # noqa: E402
from app.auth import create_session, get_or_create_user  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.entitlements import resolve  # noqa: E402
from app.models import Subscription, User  # noqa: E402

client = TestClient(main.app)


def _login(email: str) -> str:
    db = SessionLocal()
    user = get_or_create_user(db, email)
    token = create_session(db, user)
    uid = user.id
    db.close()
    client.cookies.set("pdf2word_session", token)
    return uid


def _sign(payload: bytes) -> str:
    ts = int(time.time())
    signed = f"{ts}.".encode() + payload
    sig = hmac.new(WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def _sub_event(customer_id, sub_id, status, period_end, price="price_monthly",
               etype="customer.subscription.updated"):
    return {
        "id": "evt_" + sub_id,
        "object": "event",
        "type": etype,
        "data": {"object": {
            "id": sub_id,
            "object": "subscription",
            "customer": customer_id,
            "status": status,
            "current_period_end": period_end,
            "items": {"data": [{"price": {"id": price}}]},
        }},
    }


def test_checkout_requires_auth():
    client.cookies.clear()
    r = client.post("/api/billing/checkout", json={"plan": "monthly"})
    assert r.status_code == 401


def test_checkout_creates_customer_and_session(monkeypatch):
    _login("pay@example.com")
    monkeypatch.setattr(stripe.Customer, "create",
                        lambda **kw: {"id": "cus_ABC"})
    monkeypatch.setattr(stripe.checkout.Session, "create",
                        lambda **kw: {"id": "cs_1", "url": "https://checkout.test/pay"})
    r = client.post("/api/billing/checkout", json={"plan": "monthly"})
    assert r.status_code == 200
    assert r.json()["url"] == "https://checkout.test/pay"
    db = SessionLocal()
    u = db.query(User).filter(User.email == "pay@example.com").one()
    assert u.stripe_customer_id == "cus_ABC"
    db.close()
    client.cookies.clear()


def test_webhook_activates_then_cancels_subscription():
    uid = _login("sub@example.com")
    # give the user a known stripe customer id (normally set at checkout)
    db = SessionLocal()
    u = db.query(User).filter(User.id == uid).one()
    u.stripe_customer_id = "cus_SUB"
    db.commit()
    db.close()

    future = int(time.time()) + 100000
    payload = json.dumps(_sub_event("cus_SUB", "sub_1", "active", future)).encode()
    r = client.post("/api/webhooks/stripe", content=payload,
                    headers={"stripe-signature": _sign(payload)})
    assert r.status_code == 200 and r.json() == {"received": True}

    db = SessionLocal()
    u = db.query(User).filter(User.id == uid).one()
    row = db.query(Subscription).filter(Subscription.stripe_subscription_id == "sub_1").one()
    assert row.status == "active" and row.plan == "pro_monthly"
    assert resolve(db, u).tier == "pro"
    db.close()

    # cancel: same subscription id, status canceled -> back to free
    payload2 = json.dumps(
        _sub_event("cus_SUB", "sub_1", "canceled", future,
                   etype="customer.subscription.deleted")
    ).encode()
    r2 = client.post("/api/webhooks/stripe", content=payload2,
                     headers={"stripe-signature": _sign(payload2)})
    assert r2.status_code == 200
    db = SessionLocal()
    u = db.query(User).filter(User.id == uid).one()
    assert resolve(db, u).tier == "free"
    db.close()
    client.cookies.clear()


def test_webhook_rejects_bad_signature():
    payload = b'{"id":"evt_x","type":"customer.subscription.updated","data":{"object":{}}}'
    r = client.post("/api/webhooks/stripe", content=payload,
                    headers={"stripe-signature": "t=1,v1=deadbeef"})
    assert r.status_code == 400

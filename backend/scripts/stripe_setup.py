#!/usr/bin/env python3
"""One-shot, idempotent Stripe setup for pdf2word Pro.

Runs against YOUR Stripe account using YOUR key — the key is read from the
environment and never leaves your machine. Safe to re-run: it reuses existing
objects (matched by lookup key / URL) instead of creating duplicates.

Creates:
  - Product "pdf2word Pro"
  - Price  monthly  (lookup_key: pdf2word_pro_monthly)
  - Price  annual   (lookup_key: pdf2word_pro_annual)
  - (optional) a webhook endpoint, if --webhook-url is given

Then prints the env vars to paste into Render.

Usage:
  export STRIPE_SECRET_KEY=sk_test_...          # TEST key first!
  python scripts/stripe_setup.py                                  # products + prices
  python scripts/stripe_setup.py --monthly-cents 400 --annual-cents 3900
  python scripts/stripe_setup.py --webhook-url https://your-api.onrender.com/api/webhooks/stripe
"""
from __future__ import annotations

import argparse
import os
import sys

import stripe

PRODUCT_NAME = "pdf2word Pro"
PRODUCT_KEY = "pdf2word_pro"                 # stored in product metadata for idempotency
MONTHLY_LOOKUP = "pdf2word_pro_monthly"
ANNUAL_LOOKUP = "pdf2word_pro_annual"
WEBHOOK_EVENTS = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
]


def _find_product() -> stripe.Product | None:
    for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        if p.get("metadata", {}).get("app_key") == PRODUCT_KEY:
            return p
    return None


def _ensure_product() -> stripe.Product:
    existing = _find_product()
    if existing:
        print(f"  product exists: {existing['id']}")
        return existing
    p = stripe.Product.create(name=PRODUCT_NAME, metadata={"app_key": PRODUCT_KEY})
    print(f"  product created: {p['id']}")
    return p


def _ensure_price(product_id: str, lookup: str, amount_cents: int, interval: str) -> stripe.Price:
    found = stripe.Price.list(lookup_keys=[lookup], limit=1).data
    if found:
        print(f"  price exists ({lookup}): {found[0]['id']}")
        return found[0]
    price = stripe.Price.create(
        product=product_id,
        unit_amount=amount_cents,
        currency="usd",
        recurring={"interval": interval},
        lookup_key=lookup,
    )
    print(f"  price created ({lookup}): {price['id']}  = ${amount_cents/100:.2f}/{interval}")
    return price


def _ensure_webhook(url: str) -> stripe.WebhookEndpoint:
    for w in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
        if w.get("url") == url:
            print(f"  webhook exists: {w['id']} (secret shown only at creation — "
                  "roll it in the dashboard if you need it again)")
            return w
    w = stripe.WebhookEndpoint.create(url=url, enabled_events=WEBHOOK_EVENTS)
    print(f"  webhook created: {w['id']}")
    return w


def main() -> int:
    ap = argparse.ArgumentParser(description="Set up pdf2word Pro in Stripe.")
    ap.add_argument("--monthly-cents", type=int, default=400, help="monthly price in cents (default 400 = $4.00)")
    ap.add_argument("--annual-cents", type=int, default=3900, help="annual price in cents (default 3900 = $39.00)")
    ap.add_argument("--webhook-url", default=None, help="create/find a webhook endpoint at this URL")
    args = ap.parse_args()

    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        print("ERROR: set STRIPE_SECRET_KEY (use your TEST key first).", file=sys.stderr)
        return 2
    stripe.api_key = key
    mode = "TEST" if "_test_" in key else "LIVE"
    print(f"Using Stripe {mode} key.")
    if mode == "LIVE":
        confirm = input("This is a LIVE key. Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            return 1

    print("Products & prices:")
    product = _ensure_product()
    monthly = _ensure_price(product["id"], MONTHLY_LOOKUP, args.monthly_cents, "month")
    annual = _ensure_price(product["id"], ANNUAL_LOOKUP, args.annual_cents, "year")

    webhook_secret = None
    if args.webhook_url:
        print("Webhook:")
        wh = _ensure_webhook(args.webhook_url)
        webhook_secret = wh.get("secret")  # only present when just created

    print("\n" + "=" * 60)
    print("Set these env vars (Render dashboard, all secret):")
    print(f"  STRIPE_SECRET_KEY = {key[:12]}…  (the key you just used)")
    print(f"  STRIPE_PRICE_MONTHLY = {monthly['id']}")
    print(f"  STRIPE_PRICE_ANNUAL  = {annual['id']}")
    if webhook_secret:
        print(f"  STRIPE_WEBHOOK_SECRET = {webhook_secret}")
    elif args.webhook_url:
        print("  STRIPE_WEBHOOK_SECRET = (endpoint already existed — copy it from the")
        print("                           Stripe dashboard → Developers → Webhooks)")
    else:
        print("  STRIPE_WEBHOOK_SECRET = (run again with --webhook-url, or create the")
        print("                           endpoint in the dashboard and copy its secret)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Workstream C: per-tier limits enforced in the convert path.

Unit tests cover validate_pdf's parameterized limits. Integration tests use
a freshly-reloaded app (fresh rate limiter) so they don't interfere with the
shared limiter state of other test modules.
"""
import importlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.validation import PdfValidationError, validate_pdf


# ---------- unit: parameterized limits ----------

def test_size_limit_enforced(text_pdf):
    with pytest.raises(PdfValidationError) as e:
        validate_pdf(text_pdf, max_file_size_bytes=10)
    assert e.value.code == "TOO_LARGE"


def test_pages_limit_enforced(many_pages_pdf):
    with pytest.raises(PdfValidationError) as e:
        validate_pdf(many_pages_pdf, max_pages=100)   # 101-page doc
    assert e.value.code == "TOO_MANY_PAGES"
    # Pro's higher cap admits it
    validate_pdf(many_pages_pdf, max_pages=500)


def test_ocr_pages_limit_enforced(scanned_pdf_many_pages):
    with pytest.raises(PdfValidationError) as e:
        validate_pdf(scanned_pdf_many_pages, max_ocr_pages=20)   # 21 image-only pages
    assert e.value.code == "TOO_MANY_PAGES_OCR"
    assert validate_pdf(scanned_pdf_many_pages, max_ocr_pages=200) is True


# ---------- integration helpers ----------

def _fresh_app(monkeypatch, rate_limit="1000/hour"):
    monkeypatch.setenv("RATE_LIMIT", rate_limit)
    from app import config, main
    importlib.reload(config)
    importlib.reload(main)
    return main


def _make_pro(main_mod, client, email):
    from app.auth import create_session, get_or_create_user
    from app.db import SessionLocal
    from app.models import Subscription
    db = SessionLocal()
    u = get_or_create_user(db, email)
    token = create_session(db, u)
    db.add(Subscription(
        user_id=u.id, stripe_subscription_id="sub_" + email,
        status="active", plan="pro_monthly",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    db.commit()
    db.close()
    client.cookies.set("pdf2word_session", token)


@pytest.fixture(autouse=True)
def _restore(monkeypatch):
    yield
    # reset module state to defaults for other test files
    from app import config, main
    importlib.reload(config)
    importlib.reload(main)


# ---------- integration: tier enforcement in /api/convert ----------

def test_convert_pages_gated_by_tier(monkeypatch, many_pages_pdf):
    main = _fresh_app(monkeypatch)
    client = TestClient(main.app)
    files = {"file": ("a.pdf", many_pages_pdf, "application/pdf")}

    client.cookies.clear()
    r = client.post("/api/convert", files=files)
    assert r.status_code == 400 and r.json()["code"] == "TOO_MANY_PAGES"

    _make_pro(main, client, "pro-pages@example.com")
    r2 = client.post("/api/convert", files={"file": ("a.pdf", many_pages_pdf, "application/pdf")})
    assert r2.status_code == 200


def test_pro_exempt_from_rate_limit(monkeypatch, text_pdf):
    main = _fresh_app(monkeypatch, rate_limit="2/hour")
    client = TestClient(main.app)
    f = lambda: {"file": ("a.pdf", text_pdf, "application/pdf")}

    client.cookies.clear()
    assert client.post("/api/convert", files=f()).status_code == 200
    assert client.post("/api/convert", files=f()).status_code == 200
    assert client.post("/api/convert", files=f()).status_code == 429   # free cap hit

    _make_pro(main, client, "pro-rl@example.com")
    for _ in range(3):
        assert client.post("/api/convert", files=f()).status_code == 200   # exempt

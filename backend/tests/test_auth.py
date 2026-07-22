"""End-to-end magic-link auth tests (SQLite + FastAPI TestClient).

Run with the console email backend so the sign-in link is printed and can be
captured; a generous rate limit avoids tripping the per-IP throttle in tests.
"""
import re

import pytest
from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)

LINK_RE = re.compile(r"/api/auth/verify\?token=([A-Za-z0-9_\-]+)")


def _request_and_capture(email: str, capsys) -> str:
    r = client.post("/api/auth/request-link", json={"email": email})
    assert r.status_code == 200 and r.json() == {"ok": True}
    out = capsys.readouterr().out
    m = LINK_RE.search(out)
    assert m, f"no magic link printed: {out!r}"
    return m.group(1)


def test_request_link_always_ok_even_for_garbage(capsys):
    r = client.post("/api/auth/request-link", json={"email": "not-an-email"})
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_full_login_flow(capsys):
    token = _request_and_capture("alice@example.com", capsys)
    r = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert r.status_code == 303
    assert main.app  # sanity
    assert "pdf2word_session" in r.cookies or any(
        "pdf2word_session" in c for c in r.headers.get_list("set-cookie")
    )
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"
    client.cookies.clear()


def test_verify_rejects_bad_token():
    r = client.get("/api/auth/verify?token=totally-bogus", follow_redirects=False)
    assert r.status_code == 400
    assert r.json()["code"] == "BAD_LINK"


def test_magic_link_is_single_use(capsys):
    token = _request_and_capture("bob@example.com", capsys)
    first = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert first.status_code == 303
    client.cookies.clear()
    second = client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert second.status_code == 400
    client.cookies.clear()


def test_logout_clears_session(capsys):
    token = _request_and_capture("carol@example.com", capsys)
    client.get(f"/api/auth/verify?token={token}", follow_redirects=False)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401


def test_anonymous_is_default():
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/health").status_code == 200

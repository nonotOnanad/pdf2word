"""Cross-origin cookie + CORS credential behavior (prod config)."""
import importlib
import re

from fastapi.testclient import TestClient


def _reload():
    import app.config, app.auth_routes, app.main
    importlib.reload(app.config)
    importlib.reload(app.auth_routes)
    importlib.reload(app.main)
    return app


def test_prod_cookie_is_samesite_none_and_secure(monkeypatch, capsys):
    monkeypatch.setenv("SESSION_COOKIE_SAMESITE", "none")
    monkeypatch.setenv("AUTH_REQUEST_MAX_PER_HOUR", "1000")
    monkeypatch.setenv("EMAIL_PROVIDER", "console")
    app = _reload()
    try:
        c = TestClient(app.main.app)
        c.post("/api/auth/request-link", json={"email": "cors@example.com"})
        token = re.search(r"token=([A-Za-z0-9_\-]+)", capsys.readouterr().out).group(1)
        r = c.get(f"/api/auth/verify?token={token}", follow_redirects=False)
        set_cookie = " ".join(r.headers.get_list("set-cookie")).lower()
        assert "samesite=none" in set_cookie
        assert "secure" in set_cookie
    finally:
        # restore default module state so later tests see the default app
        monkeypatch.undo()
        _reload()


def test_cors_allows_credentials():
    app = _reload()
    c = TestClient(app.main.app)
    r = c.options(
        "/api/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-credentials") == "true"
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"

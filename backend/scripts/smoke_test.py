#!/usr/bin/env python3
"""Post-deploy smoke test for pdf2word — dependency-free (stdlib only).

Checks the deployed API is up and correctly wired, especially the cross-origin
pieces that are easy to get wrong. It does NOT complete the email click-through
(that needs a human); it verifies everything up to and around it.

Usage:
  python scripts/smoke_test.py --api https://your-api.onrender.com \
      --origin https://pdf2word-silk.vercel.app --email you@example.com

  --api     required: deployed backend base URL
  --origin  optional: frontend origin, to verify CORS credentials + echo
  --email   optional: if given, tests request-link (SENDS A REAL EMAIL in prod)
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))


def _req(url, method="GET", headers=None, data=None):
    r = urllib.request.Request(url, method=method, headers=headers or {}, data=data)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception as e:  # noqa: BLE001
        return None, {}, str(e).encode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True, help="deployed backend base URL")
    ap.add_argument("--origin", default=None, help="frontend origin for CORS check")
    ap.add_argument("--email", default=None, help="test request-link (sends a real email in prod)")
    args = ap.parse_args()
    api = args.api.rstrip("/")

    # 1. health
    st, _, body = _req(f"{api}/api/health")
    ok = st == 200 and b'"ok"' in body
    record("health 200", ok, f"status={st}")

    # 2. anonymous /me is 401
    st, _, _ = _req(f"{api}/api/auth/me")
    record("anonymous /me is 401", st == 401, f"status={st}")

    # 3. CORS preflight: credentials allowed + origin echoed
    if args.origin:
        st, hdrs, _ = _req(
            f"{api}/api/auth/me", method="OPTIONS",
            headers={"Origin": args.origin, "Access-Control-Request-Method": "GET"},
        )
        h = {k.lower(): v for k, v in hdrs.items()}
        cred = h.get("access-control-allow-credentials") == "true"
        echo = h.get("access-control-allow-origin") == args.origin
        record("CORS allow-credentials=true", cred, h.get("access-control-allow-credentials"))
        record("CORS allow-origin echoes frontend", echo, h.get("access-control-allow-origin"))
    else:
        record("CORS check", True, "skipped (no --origin)")

    # 4. webhook rejects a bad signature (400)
    st, _, _ = _req(
        f"{api}/api/webhooks/stripe", method="POST",
        headers={"Stripe-Signature": "t=1,v1=bad", "Content-Type": "application/json"},
        data=b"{}",
    )
    record("webhook rejects bad signature (400)", st == 400, f"status={st}")

    # 5. request-link is 200 (optional; sends a real email in prod)
    if args.email:
        st, _, body = _req(
            f"{api}/api/auth/request-link", method="POST",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"email": args.email}).encode(),
        )
        ok = st == 200 and b'"ok"' in body
        record("request-link 200 (email sent)", ok, f"status={st}")
    else:
        record("request-link", True, "skipped (no --email)")

    # report
    print("\npdf2word smoke test —", api)
    print("-" * 52)
    worst_ok = True
    for status, name, detail in results:
        mark = "✓" if status == PASS else "✗"
        line = f"  {mark} {status}  {name}"
        if detail:
            line += f"   ({detail})"
        print(line)
        if status == FAIL:
            worst_ok = False
    print("-" * 52)
    print("RESULT:", "ALL PASS ✅" if worst_ok else "FAILURES ❌")
    if worst_ok and args.email:
        print("\nNext (manual): open the emailed link, then confirm /api/auth/me shows you")
        print("signed in from the frontend, and that Upgrade → Stripe Checkout works.")
    return 0 if worst_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

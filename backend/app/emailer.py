"""Transactional email abstraction for magic links.

Dev default is the console backend (prints the link) so the whole auth flow
runs with zero external setup. Set EMAIL_PROVIDER=resend + RESEND_API_KEY for
production.
"""
from __future__ import annotations

import os

import httpx


class EmailError(Exception):
    pass


def send_magic_link(to_email: str, link: str) -> None:
    provider = os.environ.get("EMAIL_PROVIDER", "console").lower()
    subject = "Your pdf2word sign-in link"
    text = (f"Click to sign in to pdf2word:\n\n{link}\n\n"
            "This link expires shortly and can be used once. "
            "If you didn't request it, ignore this email.")
    if provider == "console":
        print(f"[emailer:console] To: {to_email}\n{subject}\n{text}")
        return
    if provider == "resend":
        api_key = os.environ.get("RESEND_API_KEY")
        sender = os.environ.get("EMAIL_FROM", "login@pdf2word.app")
        if not api_key:
            raise EmailError("RESEND_API_KEY not set")
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"from": sender, "to": [to_email], "subject": subject, "text": text},
            timeout=10,
        )
        if resp.status_code >= 300:
            raise EmailError(f"resend error {resp.status_code}: {resp.text[:200]}")
        return
    raise EmailError(f"unknown EMAIL_PROVIDER: {provider}")

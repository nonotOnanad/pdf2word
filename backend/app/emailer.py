"""Transactional email abstraction for magic links.

Dev default is the console backend (prints the link) so the whole auth flow
runs with zero external setup. Set EMAIL_PROVIDER=resend + RESEND_API_KEY for
production.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("pdf2word.emailer")

# Free-mail domains can never be verified as a Resend *sender* — Resend rejects
# them with 403 "Domain not verified". Sending FROM gmail.com is impossible;
# only a domain you control can be verified. Fall back to Resend's shared test
# sender so a misconfiguration degrades instead of silently failing.
UNVERIFIABLE_SENDER_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com",
    "outlook.com", "live.com", "icloud.com", "aol.com", "proton.me",
}
RESEND_TEST_SENDER = "onboarding@resend.dev"


class EmailError(Exception):
    pass


def _safe_sender(sender: str) -> str:
    """Swap an impossible sender for Resend's test sender, loudly."""
    domain = sender.rsplit("@", 1)[-1].lower() if "@" in sender else ""
    if domain in UNVERIFIABLE_SENDER_DOMAINS:
        logger.warning(
            "EMAIL_FROM=%r uses %s, which cannot be verified as a sender. "
            "Falling back to %s (delivers only to your Resend account email). "
            "Set EMAIL_FROM to an address on a domain verified in Resend.",
            sender, domain, RESEND_TEST_SENDER,
        )
        return RESEND_TEST_SENDER
    return sender


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
        sender = _safe_sender(os.environ.get("EMAIL_FROM", RESEND_TEST_SENDER))
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

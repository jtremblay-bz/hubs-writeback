"""Signed personal links. A link is `<slug>.<expiry>.<signature>`: it names one page, expires, and cannot be forged
without DEAL_UPDATE_SIGNING_SECRET. Anyone holding a link can act as that page's person, so treat it like a password."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time


def _secret() -> bytes:
    s = os.environ.get("DEAL_UPDATE_SIGNING_SECRET", "")
    if len(s) < 16:
        raise RuntimeError("DEAL_UPDATE_SIGNING_SECRET must be set (16+ characters).")
    return s.encode()


def _sig(msg: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(_secret(), msg.encode(), hashlib.sha256).digest()[:18]).decode().rstrip("=")


def sign(slug: str, days: int = 60) -> str:
    msg = f"{slug}.{int(time.time()) + days * 86400}"
    return f"{msg}.{_sig(msg)}"


def verify(token: str) -> str | None:
    """Return the slug for a valid, unexpired token, else None."""
    try:
        slug, exp, sig = token.rsplit(".", 2)
        if not hmac.compare_digest(sig, _sig(f"{slug}.{exp}")) or int(exp) < time.time():
            return None
        return slug
    except Exception:
        return None

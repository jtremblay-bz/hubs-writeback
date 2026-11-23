"""Who may approve what.

A deal's AE rows (the activity log, next step, MEDDPICC, forecast, security status) may be approved by the
deal's HubSpot owner. POV rows (risk score, risk notes, customer POV champion) may be approved by the deal's
technical owner (the SE). A short list of administrators may approve either, so a manager can decide on a rep's
behalf and so rehearsals work.

Identity comes from the artifact page: it records the viewer's opaque id, and the artifact database resolves that
id to a display name. This module matches that name to HubSpot's owner records. A name is weaker than a signed
Slack payload, so a decision whose approver cannot be matched is held, never written.
"""
from __future__ import annotations

import re

ADMINS = {"joe tremblay"}   # may approve any part; edit here, or load from config later

AE_PART, POV_PART = "deal", "pov"


def norm(name: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def owner_name(owners: dict[str, dict], owner_id: str | None) -> str:
    """owners: HubSpot owner id -> {"name": ..., "email": ...}."""
    return (owners.get(str(owner_id or "")) or {}).get("name", "")


def can_approve(part: str, approver_name: str, deal: dict, owners: dict[str, dict]) -> tuple[bool, str]:
    """Return (allowed, reason). `deal` carries hubspot_owner_id and technical_owner."""
    who = norm(approver_name)
    if not who:
        return False, "approver's name could not be resolved"
    if who in {norm(a) for a in ADMINS}:
        return True, "administrator"
    if part == POV_PART:
        want, role = owner_name(owners, deal.get("technical_owner")), "SE (technical owner)"
    else:
        want, role = owner_name(owners, deal.get("hubspot_owner_id")), "deal owner"
    if not want:
        return False, f"the deal has no {role} to match against"
    if norm(want) == who:
        return True, role
    return False, f"{approver_name} is not the {role} ({want})"

"""Read-only HubSpot access for the deal-update run.

The only request this module can make is a GET. It exists so the executor can re-read a deal
right before acting (the freshness check) without any path to a write.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:  # dotenv is optional; the environment may already be set
    pass


def get_deal(deal_id: str, props: list[str], token_env: str = "HUBSPOT_PROD_TOKEN") -> dict[str, str]:
    token = os.environ.get(token_env, "")
    if not token:
        raise RuntimeError(f"{token_env} is not set")
    url = ("https://api.hubapi.com/crm/v3/objects/deals/"
           f"{urllib.parse.quote(str(deal_id))}?properties={urllib.parse.quote(','.join(props))}")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    return {k: (v if v is not None else "") for k, v in (data.get("properties") or {}).items()}

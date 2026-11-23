"""Sandbox-only HubSpot writer for the deal-update rehearsal.

This is NOT the production writer. It can only reach sandbox portal 52236613 and only deals whose
name starts with "TEST -". Production writes stay disabled in executor.PROD_WRITES_ENABLED.

write_deal() maps dropdown labels to HubSpot's internal option values, PATCHes the deal, reads it
back and reports any field that did not stick.
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.request

SANDBOX_PORTAL = "52236613"
TEST_PREFIX = "TEST -"
API = "https://api.hubapi.com"


class WriteRefused(RuntimeError):
    pass


def _token() -> str:
    if os.environ.get("HUBSPOT_PORTAL_ID", "") != SANDBOX_PORTAL:
        raise WriteRefused(f"HUBSPOT_PORTAL_ID is not the sandbox ({SANDBOX_PORTAL}); refusing to write.")
    tok = os.environ.get("HUBSPOT_TOKEN", "")
    if not tok:
        raise WriteRefused("HUBSPOT_TOKEN is not set.")
    return tok


def _call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + _token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HubSpot {e.code}: {e.read().decode()[:300]}") from None


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s or ""))).strip()


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _enum_map(prop: str) -> dict[str, str]:
    """label or value (punctuation ignored) -> internal option value."""
    d = _call("GET", f"/crm/v3/properties/deals/{prop}")
    m: dict[str, str] = {}
    for o in d.get("options", []):
        m[_key(o["label"])] = o["value"]
        m[_key(o["value"])] = o["value"]
    return m


def to_html(text: str) -> str:
    """Deal Notes is an HTML field: keep headings bold and lines separate."""
    out = []
    for ln in text.strip().splitlines():
        e = html.escape(ln)
        out.append(f"<b>{e}</b>" if ln and not ln.startswith(("-", " ")) and len(ln) < 60 else e)
    return "<br>".join(out)


def write_deal(deal_id: str, values: dict[str, str]) -> dict:
    """PATCH `values` onto a sandbox test deal. Returns {written, not_stuck, skipped}."""
    d = _call("GET", f"/crm/v3/objects/deals/{deal_id}?properties=dealname")
    name = (d.get("properties") or {}).get("dealname") or ""
    if not name.startswith(TEST_PREFIX):
        raise WriteRefused(f"Deal {deal_id} is named {name!r}, not a '{TEST_PREFIX}' test deal; refusing to write.")
    props: dict[str, str] = {}
    skipped: list[dict] = []
    enums = {f: None for f in ("hs_manual_forecast_category", "security_review_status")}
    for f, v in values.items():
        if f in enums:
            if enums[f] is None:
                enums[f] = _enum_map(f)
            val = enums[f].get(_key(v))
            if val is None:
                skipped.append({"field": f, "reason": f"{v!r} is not an option on this dropdown"})
                continue
            props[f] = val
        elif f == "deal_notes":
            props[f] = to_html(v)
        else:
            props[f] = v
    if props:
        _call("PATCH", f"/crm/v3/objects/deals/{deal_id}", {"properties": props})
    back = _call("GET", f"/crm/v3/objects/deals/{deal_id}?properties=" + ",".join(props))["properties"] if props else {}
    not_stuck = [f for f, v in props.items() if _norm(back.get(f)) != _norm(v)]
    return {"written": [f for f in props if f not in not_stuck], "not_stuck": not_stuck, "skipped": skipped, "deal_name": name}

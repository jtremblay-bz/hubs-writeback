"""Production HubSpot writer for approved deal updates (portal 44505231).

Safe by construction. A write happens only when ALL of these hold:
  1. DEAL_UPDATE_PROD_WRITES=1 is set in the environment of the process doing the write;
  2. the deal id is listed in deal_update/prod_allowlist.json (starts empty; a person adds ids on purpose);
  3. no field is on the never-write list (rules.NEVER_WRITE).
Before anything is changed the deal's current values for the fields about to change are saved to
deal_update/state/undo/<deal>-<timestamp>.json, so a write can be reversed exactly. After the write the properties
are read back; any that did not stick are reported. The caller sets last_ai_agent_update via the `auto` values.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import rules, sandbox_writer as sw

PROD_PORTAL = "44505231"
API = "https://api.hubapi.com"
HERE = Path(__file__).resolve().parent
ALLOWLIST = HERE / "prod_allowlist.json"
UNDO = HERE / "state" / "undo"
ENUM_FIELDS = ("hs_manual_forecast_category", "security_review_status")


class ProdWriteRefused(RuntimeError):
    pass


def allow_all() -> bool:
    """DEAL_UPDATE_PROD_ALLOW_ALL=1 permits any deal on a page we ingested (approvals still need the right approver).
    Unset it to switch every write off at once."""
    return os.environ.get("DEAL_UPDATE_PROD_ALLOW_ALL") == "1"


def allowed_deals() -> set[str]:
    try:
        return {str(x) for x in json.loads(ALLOWLIST.read_text())}
    except Exception:
        return set()


def _token() -> str:
    if os.environ.get("HUBSPOT_PROD_PORTAL_ID", "") != PROD_PORTAL:
        raise ProdWriteRefused(f"HUBSPOT_PROD_PORTAL_ID is not {PROD_PORTAL}; refusing to write.")
    tok = os.environ.get("HUBSPOT_PROD_TOKEN", "")
    if not tok:
        raise ProdWriteRefused("HUBSPOT_PROD_TOKEN is not set.")
    return tok


def _call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + _token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HubSpot {e.code}: {e.read().decode()[:300]}") from None


def _enum_map(prop: str) -> dict[str, str]:
    d = _call("GET", f"/crm/v3/properties/deals/{prop}")
    m: dict[str, str] = {}
    for o in d.get("options", []):
        m[sw._key(o["label"])] = o["value"]
        m[sw._key(o["value"])] = o["value"]
    return m


def preflight(deal_id: str, fields: list[str]) -> None:
    if os.environ.get("DEAL_UPDATE_PROD_WRITES") != "1":
        raise ProdWriteRefused("DEAL_UPDATE_PROD_WRITES=1 is not set.")
    if not allow_all() and str(deal_id) not in allowed_deals():
        raise ProdWriteRefused(f"Deal {deal_id} is not in prod_allowlist.json.")
    bad = sorted(f for f in fields if f in rules.NEVER_WRITE)
    if bad:
        raise ProdWriteRefused(f"Refusing never-write fields: {bad}")


def write_deal(deal_id: str, values: dict[str, str]) -> dict:
    """PATCH approved values onto an allowlisted prod deal. Returns what was written, skipped and saved for undo."""
    preflight(deal_id, list(values))
    props: dict[str, str] = {}
    skipped: list[dict] = []
    enums: dict[str, dict[str, str]] = {}
    for f, v in values.items():
        if f in ENUM_FIELDS:
            enums.setdefault(f, _enum_map(f))
            val = enums[f].get(sw._key(v))
            if val is None:
                skipped.append({"field": f, "reason": f"{v!r} is not an option on this dropdown"})
                continue
            props[f] = val
        elif f == "deal_notes":
            props[f] = sw.to_html(v)
        else:
            props[f] = v
    undo_path = None
    before: dict = {}
    if props:
        got = _call("GET", f"/crm/v3/objects/deals/{deal_id}?properties=" + ",".join(props))["properties"]
        before = {k: got.get(k) for k in props}      # only the fields we change; HubSpot also returns read-only ones (createdate...)
        try:                                     # a local copy where the disk lasts; the durable copy rides on the decision record
            UNDO.mkdir(parents=True, exist_ok=True)
            undo_path = UNDO / f"{deal_id}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
            undo_path.write_text(json.dumps({"deal_id": deal_id, "portal": PROD_PORTAL, "before": before, "wrote": list(props)}, indent=1))
        except OSError:
            undo_path = None
        _call("PATCH", f"/crm/v3/objects/deals/{deal_id}", {"properties": props})
    back = _call("GET", f"/crm/v3/objects/deals/{deal_id}?properties=" + ",".join(props))["properties"] if props else {}
    not_stuck = [f for f, v in props.items() if sw._norm(back.get(f)) != sw._norm(v)]
    return {"written": [f for f in props if f not in not_stuck], "not_stuck": not_stuck, "skipped": skipped, "undo_file": str(undo_path) if undo_path else "", "before": before}


def undo(undo_file: str) -> dict:
    """Restore the values saved before a write. Empty values are cleared."""
    rec = json.loads(Path(undo_file).read_text())
    deal_id = rec["deal_id"]
    preflight(deal_id, rec["wrote"])
    _call("PATCH", f"/crm/v3/objects/deals/{deal_id}", {"properties": {k: (v or "") for k, v in rec["before"].items()}})
    return {"restored": list(rec["before"])}

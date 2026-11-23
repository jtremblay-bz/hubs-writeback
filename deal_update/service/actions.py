"""Approve, edit or decline a proposal. This is the only place the web app causes a HubSpot write."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from datetime import date, datetime

from .. import approvers, executor, hubspot_ro, prod_writer
from ..proposals import build_prop

_owners = {"at": 0.0, "data": {}}
_lock = threading.Lock()


def get_owners() -> dict:
    if _owners["data"] and time.time() - _owners["at"] < 3600:
        return _owners["data"]
    req = urllib.request.Request("https://api.hubapi.com/crm/v3/owners?limit=500", headers={"Authorization": "Bearer " + os.environ["HUBSPOT_PROD_TOKEN"]})
    res = json.load(urllib.request.urlopen(req, timeout=30))["results"]
    _owners.update(at=time.time(), data={str(o["id"]): {"name": f'{o.get("firstName","")} {o.get("lastName","")}'.strip(), "email": o.get("email", "")} for o in res})
    return _owners["data"]


def doc_id_for(deal_id: str, part: str) -> str:
    return deal_id if part == "deal" else f"{deal_id}-pov"


def apply(store, page: dict, rep_name: str, doc_id: str, action: str, edits: dict | None, comment: str) -> dict:
    """Process one decision and save it with its result. Never raises: problems become a result the rep can read."""
    part = "pov" if doc_id.endswith("-pov") else "deal"
    deal_id = doc_id[:-4] if part == "pov" else doc_id
    deal = next((d for d in page["deals"] if d["id"] == deal_id), None)
    now = datetime.now()
    base = {"decision": action, "by": rep_name, "at": now.isoformat(timespec="seconds"), "comment": (comment or "")[:500],
            "asof": page["meta"]["asof"], "deal": deal_id, "part": part, "edits": edits or {}}
    if not deal:
        return {**base, "result": {"status": "error", "reason": "That deal is not on this page."}}
    portal = deal.get("portal", "prod")
    token_env = "HUBSPOT_TOKEN" if portal == "sandbox" else "HUBSPOT_PROD_TOKEN"
    with _lock:
        prev = store.get_decision(doc_id) or {}
        if (prev.get("result") or {}).get("status") in ("written", "partial") and prev.get("asof") == base["asof"] and action != "decline":
            return prev                                            # already written for this proposal: never write twice
        try:
            live = hubspot_ro.get_deal(deal_id, ["hubspot_owner_id", "technical_owner"], token_env=token_env)
            if portal == "sandbox":
                ok, why = (rep_name == deal.get("owner")), "test deal owner"
            else:
                ok, why = approvers.can_approve(part, rep_name, live, get_owners())
            if not ok:
                rec = {**base, "result": {"status": "held", "reason": "You are not the right person to approve this: " + why}}
            elif action == "decline":
                rec = {**base, "result": {"status": "declined", "at": base["at"]}}
            else:
                prop = build_prop(deal, part, doc_id)
                errs = executor.validate_edits(prop, edits, date.today())
                if errs:
                    rec = {**base, "result": {"status": "fix", "reason": "Fix these, then approve again.", "errors": {k: " ".join(v) for k, v in errs.items()}}}
                else:
                    fresh = hubspot_ro.get_deal(deal_id, [r["field"] for r in prop["rows"]], token_env=token_env)
                    plan = executor.plan(prop, edits or {}, fresh, date.today(), now)
                    if plan["errors"]:
                        rec = {**base, "result": {"status": "fix", "reason": "Fix these, then approve again.", "errors": {k: " ".join(v) for k, v in plan["errors"].items()}}}
                    else:
                        act = "edited_and_approved" if edits else "approved"
                        if portal == "sandbox":
                            os.environ["DEAL_UPDATE_SANDBOX_WRITES"] = "1"
                            w = executor.write_sandbox(prop, plan, rep_name, act, edits, now)
                        else:
                            w = executor.write_prod(prop, plan, rep_name, act, edits, now)
                        rec = {**base, "result": {"status": "partial" if w["not_stuck"] else "written", "at": w["at"], "count": len(w["written"]),
                                                  "skipped": [s.get("field") for s in w["skipped"]], "not_stuck": w["not_stuck"],
                                                  "reason": ("Some fields changed in HubSpot after this was proposed and were left alone: " + ", ".join(s.get("field", "") for s in w["skipped"])) if w["skipped"] else "",
                                                  "undo_file": os.path.basename(w.get("undo_file", "") or ""), "before": w.get("before", {})}}
        except prod_writer.ProdWriteRefused as e:
            msg = str(e)
            rec = {**base, "result": {"status": "not_live" if "allowlist" in msg or "DEAL_UPDATE_PROD_WRITES" in msg else "held",
                                      "reason": "Your approval is saved, but writing to HubSpot is not switched on for this deal yet." if "allowlist" in msg or "DEAL_UPDATE_PROD_WRITES" in msg else msg}}
        except Exception as e:
            rec = {**base, "result": {"status": "error", "reason": f"Could not complete this ({type(e).__name__}). Nothing was written. {str(e)[:160]}"}}
        store.set_decision(doc_id, rec)
        return rec

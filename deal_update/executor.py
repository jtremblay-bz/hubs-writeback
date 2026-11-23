"""Turn an approved (or edited) proposal into the exact HubSpot payload, and record it. Dry run only.

plan()          validates, re-checks freshness against HubSpot, and builds the payload.
dry_run_write() appends the payload to the audit log and returns it. It never calls HubSpot.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from . import rules, store

# Flipped only after the FIN change ticket is approved and a real writer is added. While False,
# nothing in this package can reach HubSpot.
PROD_WRITES_ENABLED = False

NOT_WRITTEN = {"no change", "held"}


def norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("(empty)", "")).strip()


def effective_values(prop: dict, edits: dict | None) -> dict[str, str]:
    """field -> value that would be written. An edit overrides the proposal; a cleared edit drops the field."""
    edits = edits or {}
    out: dict[str, str] = {}
    for r in prop["rows"]:
        if r["change"] in NOT_WRITTEN:
            continue
        f = r["field"]
        if f in edits:
            if (edits[f] or "").strip() == "":
                continue
            out[f] = edits[f]
        else:
            out[f] = r["after"]
    return out


def validate_edits(prop: dict, edits: dict | None, today: date) -> dict[str, list[str]]:
    return rules.validate_all(effective_values(prop, edits), today)


def plan(prop: dict, edits: dict | None, fresh: dict | None, today: date, now: datetime) -> dict:
    """Build the payload. `fresh` is the live HubSpot values of the proposal's fields."""
    values = effective_values(prop, edits)
    errors = rules.validate_all(values, today)
    if errors:
        return {"payload": {}, "auto": {}, "skipped": [], "errors": errors}
    rows = {r["field"]: r for r in prop["rows"]}
    payload: dict[str, str] = {}
    skipped: list[dict] = []
    fresh = fresh or {}
    for f, v in values.items():
        current = fresh.get(f, "")
        if norm(current) != norm(rows[f]["before"]):
            skipped.append({"field": f, "reason": "changed in HubSpot since this proposal was made",
                            "current": norm(current)[:160]})
            continue
        if f == "blitzy_activity_log":
            stamp = f"(owner-approved in Deal Update, {now:%m/%d})"
            lines = [(ln.rstrip() + " " + stamp) if ln.strip().startswith("Update:") else ln
                     for ln in v.strip().splitlines()]
            entry = "\n".join(lines).strip()
            payload[f] = entry + ("\n\n" + current.strip() if current.strip() else "")
        elif f == "next_step_date":
            payload[f] = rules.parse_date(v).isoformat()
        else:
            payload[f] = v.strip()
    auto = dict(prop.get("auto") or {})
    stamp = now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")   # a naive `now` is local time: convert, never relabel
    if auto:
        auto["deal_summary_updated"] = stamp
    if payload or auto:
        auto["last_ai_agent_update"] = stamp   # when the last approved write happened, for tracking
    return {"payload": payload, "auto": auto, "skipped": skipped, "errors": {}}


def dry_run_write(prop: dict, result: dict, approver: str, action: str, edits: dict | None, now: datetime) -> dict:
    if PROD_WRITES_ENABLED:
        raise NotImplementedError("Production writes are not implemented. Add a writer after the FIN ticket.")
    record = {
        "at": now.isoformat(timespec="seconds"), "proposal_id": prop["proposal_id"],
        "deal_id": prop["deal_id"], "deal_name": prop["deal_name"], "approver": approver,
        "action": action, "dry_run": True, "payload": result["payload"], "auto": result["auto"],
        "skipped": result["skipped"], "edits": edits or {},
    }
    store.log_audit(record)
    return record


def log_decline(prop: dict, approver: str, reason: str, note: str, now: datetime) -> dict:
    record = {"at": now.isoformat(timespec="seconds"), "proposal_id": prop["proposal_id"],
              "deal_id": prop["deal_id"], "deal_name": prop["deal_name"], "approver": approver,
              "action": "declined", "reason": reason, "note": note, "dry_run": True}
    store.log_audit(record)
    return record


def write_sandbox(prop: dict, result: dict, approver: str, action: str, edits: dict | None, now: datetime) -> dict:
    """Rehearsal writer: really writes to a sandbox TEST deal, nothing else.

    Refused unless DEAL_UPDATE_SANDBOX_WRITES=1 is set and the proposal is marked portal="sandbox".
    Production stays off (PROD_WRITES_ENABLED). The writer itself also refuses any non-sandbox portal
    and any deal not named "TEST - ...".
    """
    import os

    from . import sandbox_writer

    if PROD_WRITES_ENABLED:
        raise RuntimeError("PROD_WRITES_ENABLED must stay False for the sandbox rehearsal.")
    if os.environ.get("DEAL_UPDATE_SANDBOX_WRITES") != "1" or prop.get("portal") != "sandbox":
        raise RuntimeError("Sandbox writes are not enabled for this proposal.")
    values = {**result["payload"], **result["auto"]}
    outcome = sandbox_writer.write_deal(prop["deal_id"], values)
    record = {
        "at": now.isoformat(timespec="seconds"), "proposal_id": prop["proposal_id"],
        "deal_id": prop["deal_id"], "deal_name": prop["deal_name"], "approver": approver,
        "action": action, "dry_run": False, "portal": "sandbox", "payload": result["payload"],
        "auto": result["auto"], "skipped": result["skipped"] + outcome["skipped"],
        "not_stuck": outcome["not_stuck"], "edits": edits or {},
    }
    store.log_audit(record)
    return {**record, "written": outcome["written"]}


def write_prod(prop: dict, result: dict, approver: str, action: str, edits: dict | None, now: datetime) -> dict:
    """Write an approved proposal to production HubSpot. Refused unless the deal is on prod_allowlist.json and
    DEAL_UPDATE_PROD_WRITES=1; see prod_writer for the guards, the undo file and the read-back."""
    from . import prod_writer

    values = {**result["payload"], **result["auto"]}
    outcome = prod_writer.write_deal(prop["deal_id"], values)
    record = {
        "at": now.isoformat(timespec="seconds"), "proposal_id": prop["proposal_id"],
        "deal_id": prop["deal_id"], "deal_name": prop["deal_name"], "approver": approver,
        "action": action, "dry_run": False, "portal": "prod", "payload": result["payload"], "auto": result["auto"],
        "skipped": result["skipped"] + outcome["skipped"], "not_stuck": outcome["not_stuck"],
        "undo_file": outcome["undo_file"], "edits": edits or {},
    }
    store.log_audit(record)
    return {**record, "written": outcome["written"], "before": outcome.get("before", {})}

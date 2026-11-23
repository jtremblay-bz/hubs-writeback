"""Block Kit for the deal-update card and its Edit and Decline modals.

Slack limits respected: header 150 chars, section text 3000, input initial_value 3000, message 50 blocks.
"""
from __future__ import annotations

import json
import re

LABELS = {
    "blitzy_activity_log": "Activity log", "hs_next_step": "Next step", "next_step_date": "Next step date",
    "metrics": "Metrics", "economic_buyer": "Economic Buyer", "decision_criteria": "Decision Criteria",
    "decision_process": "Decision Process", "paper_process": "Paper Process", "identify_pain": "Identify Pain",
    "champion": "Champion", "competition": "Competition", "hs_manual_forecast_category": "Forecast category",
    "pov_memo_link": "POV memo link", "pov_risk_score": "POV risk score", "pov_risk_notes": "POV risk notes",
    "pov_success_criteria": "POV success criteria",
}
DECLINE_REASONS = [("Wrong", "wrong"), ("Already done", "already_done"), ("Not now", "not_now"), ("Other", "other")]
NOT_WRITTEN = {"no change", "held"}


def clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 3].rstrip() + "..."


def one_line(s: str, n: int) -> str:
    return clip(re.sub(r"\s+", " ", s or ""), n)


def label(field: str) -> str:
    return LABELS.get(field, field)


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": clip(text, 2990)}}


def _context(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": clip(text, 2990)}]}


def render(prop: dict, status: str | None = None) -> list[dict]:
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": clip(prop["title"], 150)}},
        _context(prop["subtitle"]),
        _context("_Rehearsal: approving is a dry run. Nothing is written to HubSpot._"),
    ]
    if prop.get("summary"):
        blocks += [_section("*Deal Summary (new field)*\n" + prop["summary"]), {"type": "divider"}]
    changing = [r for r in prop["rows"] if r["change"] not in NOT_WRITTEN]
    held = [r for r in prop["rows"] if r["change"] == "held"]
    unchanged = [r for r in prop["rows"] if r["change"] == "no change"]
    blocks.append(_section(f"*Proposed changes* ({len(changing)} of {len(prop['rows'])} rows)"))
    for i, r in enumerate(changing, 1):
        color = f"  `{r['color']}`" if r.get("color") else ""
        before = one_line(r["before"], 200) or "(empty)"
        after = one_line(r["after"], 700)
        blocks.append(_section(f"*{i}. {label(r['field'])}*{color}\n_Before:_ {before}\n_After:_ {after}"))
    for r in held:
        blocks.append(_section(f"*Held: {label(r['field'])}*\n{one_line(r['after'], 600)}"))
    if unchanged:
        blocks.append(_context("No change: " + ", ".join(label(r["field"]) for r in unchanged)))
    if prop.get("gate_gaps"):
        blocks.append(_section("*" + prop.get("gate_heading", "Before this deal can advance") + "*\n"
                               + "\n".join("- " + one_line(g, 240) for g in prop["gate_gaps"][:5])))
    if prop.get("flags"):
        blocks.append(_section("*Flags*\n" + "\n".join("- " + one_line(f, 280) for f in prop["flags"][:5])))
    if status:
        blocks.append({"type": "divider"})
        blocks.append(_section(status))
    else:
        pid = prop["proposal_id"]
        blocks.append({"type": "actions", "block_id": "du_actions", "elements": [
            {"type": "button", "action_id": "du:approve", "value": pid, "style": "primary",
             "text": {"type": "plain_text", "text": "Approve all"},
             "confirm": {"title": {"type": "plain_text", "text": "Approve all rows?"},
                         "text": {"type": "plain_text", "text": "Dry run: the payload is recorded, nothing is written to HubSpot."},
                         "confirm": {"type": "plain_text", "text": "Approve"},
                         "deny": {"type": "plain_text", "text": "Cancel"}}},
            {"type": "button", "action_id": "du:edit", "value": pid, "text": {"type": "plain_text", "text": "Edit"}},
            {"type": "button", "action_id": "du:decline", "value": pid, "style": "danger",
             "text": {"type": "plain_text", "text": "Decline"}},
        ]})
    return blocks


def thread_messages(prop: dict) -> list[str]:
    """Longer text that goes in the card's thread (kept out of the card so it stays readable)."""
    out = []
    if prop.get("notes_text"):
        out.append("*Deal Notes (new field, written automatically)*\n\n" + clip(prop["notes_text"], 4800))
    if prop.get("risk_notes_text"):
        out.append("*pov_risk_notes (proposed text)*\n" + clip(prop["risk_notes_text"], 4800))
    return out


def edit_modal(prop: dict, channel: str, ts: str) -> dict:
    blocks: list[dict] = [_section("Edit any value below. Clear a field to skip it. Validation runs when you save, "
                                   "and a saved edit is then approved (dry run).")]
    for r in prop["rows"]:
        if r["change"] in NOT_WRITTEN:
            continue
        el = {"type": "plain_text_input", "action_id": "v", "multiline": True}
        if r["after"]:
            el["initial_value"] = clip(r["after"], 3000)
        blocks.append({"type": "input", "block_id": f"row_{r['field']}", "optional": True,
                       "label": {"type": "plain_text", "text": label(r["field"])}, "element": el})
    return {"type": "modal", "callback_id": "du_edit",
            "title": {"type": "plain_text", "text": "Edit proposal"},
            "submit": {"type": "plain_text", "text": "Save and approve"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": json.dumps({"proposal_id": prop["proposal_id"], "channel": channel, "ts": ts}),
            "blocks": blocks}


def decline_modal(prop: dict, channel: str, ts: str) -> dict:
    return {"type": "modal", "callback_id": "du_decline",
            "title": {"type": "plain_text", "text": "Decline proposal"},
            "submit": {"type": "plain_text", "text": "Decline"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": json.dumps({"proposal_id": prop["proposal_id"], "channel": channel, "ts": ts}),
            "blocks": [
                {"type": "input", "block_id": "reason", "label": {"type": "plain_text", "text": "Why?"},
                 "element": {"type": "static_select", "action_id": "v",
                             "options": [{"text": {"type": "plain_text", "text": t}, "value": v} for t, v in DECLINE_REASONS]}},
                {"type": "input", "block_id": "note", "optional": True,
                 "label": {"type": "plain_text", "text": "Anything to add (optional)"},
                 "element": {"type": "plain_text_input", "action_id": "v", "multiline": True}},
            ]}

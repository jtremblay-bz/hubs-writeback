"""Validation for deal-update values.

Mirrors the Stage Gates and Required Fields rules (field formats, never-write list) and the
deal-update skill's non-negotiables (colored MEDDPICC values, dated single-action next step, an
activity log in the contract format, no invented approval text).
"""
from __future__ import annotations

import re
from datetime import date, datetime

# Fields the run never writes: stage, amount and close date are changed by hand; the rest are
# system-set, rep-entered, source-of-truth elsewhere (Ironclad, comp credit) or SE-owned.
NEVER_WRITE = frozenset({
    "dealstage", "amount", "closedate", "hubspot_owner_id", "dealtype", "deal_source",
    "deal_source_channel", "deal_source_group", "technical_owner", "estimated_arr", "arr_source",
    "estimated_services_revenue", "arr", "services_revenue", "term_length_months",
    "contract_executed", "order_form_attached", "current_order_form_number",
    "order_form_execution", "sourced_by",
})

MEDDPICC = ("metrics", "economic_buyer", "decision_criteria", "decision_process",
            "paper_process", "identify_pain", "champion", "competition")

COLOR_RE = re.compile(r"^(GREEN|YELLOW|RED):\s*\S")
URL_RE = re.compile(r"^https://\S+$")
DATE_IN_TEXT = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b")

# Text the skill forbids in a written value: it would record an approval that has not happened.
FORBIDDEN_PHRASES = ("(owner-approved", "(proposal only", "pending)", "not approved)",
                     "approved in session")

NEXT_STEP_MAX = 500
LONG_TEXT_MAX = 3000


def parse_date(s: str | None) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt, chunk in (("%Y-%m-%d", s[:10]), ("%m/%d/%y", s), ("%m/%d/%Y", s)):
        try:
            return datetime.strptime(chunk, fmt).date()
        except ValueError:
            continue
    return None


def dates_in_text(text: str) -> list[date]:
    out = []
    for m in DATE_IN_TEXT.findall(text or ""):
        d = parse_date(m)
        if d:
            out.append(d)
    return out


def validate_value(field: str, value: str, today: date, all_values: dict[str, str]) -> list[str]:
    """Return a list of problems with one value (empty list = fine)."""
    v = (value or "").strip()
    errs: list[str] = []
    if field in NEVER_WRITE:
        return [f"{field} is never written by this run."]
    if any(p in v.lower() for p in FORBIDDEN_PHRASES):
        errs.append("Contains approval text that has not happened yet (for example 'pending' or "
                    "'proposal only'). The run adds the real approval record itself.")
    if field in MEDDPICC:
        if not COLOR_RE.match(v):
            errs.append("Must start with GREEN:, YELLOW: or RED: followed by the reason.")
        if len(v) > LONG_TEXT_MAX:
            errs.append(f"Too long ({len(v)} characters, limit {LONG_TEXT_MAX}).")
    elif field == "hs_next_step":
        if not v:
            errs.append("Next step cannot be empty.")
        if len(v) > NEXT_STEP_MAX:
            errs.append(f"Too long ({len(v)} characters, limit {NEXT_STEP_MAX}).")
        step_date = parse_date(all_values.get("next_step_date"))
        in_text = dates_in_text(v)
        if step_date and in_text and step_date not in in_text:
            errs.append("The date in the text does not match the next step date.")
    elif field == "next_step_date":
        d = parse_date(v)
        if not d:
            errs.append("Use a date like 2026-11-24 or 11/24/26.")
        elif d <= today:
            errs.append("Must be after today.")
    elif field == "blitzy_activity_log":
        lines = [ln for ln in v.splitlines() if ln.strip()]
        if not lines or not parse_date(lines[0]):
            errs.append("First line must be the entry date (MM/DD/YY).")
        for label in ("Trend:", "Update:", "Risk:"):
            if not any(ln.strip().startswith(label) for ln in lines):
                errs.append(f"Missing a '{label}' line.")
        if len(lines) > 5:
            errs.append("An activity log entry is four lines (five only for a kept forecast override).")
    elif field == "pov_memo_link":
        if not URL_RE.match(v):
            errs.append("Must be a full https:// link.")
    elif field == "pov_risk_score":
        if v not in {"1", "2", "3", "4", "5"}:
            errs.append("Must be a whole number from 1 (lowest risk) to 5 (highest).")
    elif field in ("pov_risk_notes", "pov_success_criteria", "deal_summary", "deal_notes"):
        if not v:
            errs.append("Cannot be empty.")
    elif len(v) > LONG_TEXT_MAX * 2:
        errs.append("Too long.")
    return errs


def validate_all(values: dict[str, str], today: date | None = None) -> dict[str, list[str]]:
    today = today or date.today()
    out = {}
    for f, v in values.items():
        e = validate_value(f, v, today, values)
        if e:
            out[f] = e
    return out

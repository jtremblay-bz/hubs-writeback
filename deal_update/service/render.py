"""Server-rendered rep page. All data is escaped; no script is needed, so nothing a rep can type runs as code."""
from __future__ import annotations

import html
from pathlib import Path

LOGO = (Path(__file__).parent / "logo_b64.txt").read_text().strip()
LABEL = {"blitzy_activity_log": "Activity log", "hs_next_step": "Next step", "next_step_date": "Next step date", "metrics": "Metrics",
         "economic_buyer": "Economic Buyer", "decision_criteria": "Decision Criteria", "decision_process": "Decision Process",
         "paper_process": "Paper Process", "identify_pain": "Identify Pain", "champion": "Champion", "competition": "Competition",
         "hs_manual_forecast_category": "Forecast category", "security_review_status": "Security review", "deal_summary": "Deal Summary",
         "deal_notes": "Deal Notes", "next_stage_blockers": "Next stage criteria", "pov_risk_score": "POV risk score (1 to 5)",
         "pov_risk_notes": "POV risk notes", "customer_pov_champion": "Customer POV champion"}
AUTO = ("deal_summary", "deal_notes", "next_stage_blockers")
OPTS = {"hs_manual_forecast_category": ["PIPELINE", "BEST_CASE", "MOST_LIKELY", "COMMIT", "OMIT"],
        "security_review_status": ["Cleared", "Underway (dated path)", "Initiated (no path)", "Not started"]}
CSS = """
:root{--bg:#f4f6f8;--surface:#fff;--ink:#17212b;--muted:#596677;--line:#dbe1e8;--accent:#5c39f2;--accent-ink:#fff;--accent-soft:#edeafd;--good:#1c7647;--good-soft:#e5f4ec;--warn:#9a5b06;--warn-soft:#fbf0dc;--bad:#ad2f27;--bad-soft:#fbe9e7;color-scheme:light dark}
@media(prefers-color-scheme:dark){:root{--bg:#11171d;--surface:#19212a;--ink:#e7edf3;--muted:#9aa8b7;--line:#2a3541;--accent:#a994ff;--accent-ink:#120d2b;--accent-soft:#252040;--good:#55c58a;--good-soft:#15291f;--warn:#e2a64a;--warn-soft:#2d2412;--bad:#f08a81;--bad-soft:#321a18}}
*{box-sizing:border-box}body{background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"Segoe UI",system-ui,sans-serif;margin:0;padding:20px max(16px,env(safe-area-inset-right)) 56px max(16px,env(safe-area-inset-left))}
main{max-width:940px;margin:0 auto;display:grid;gap:16px;min-width:0}h1{font-size:26px;line-height:1.2;margin:0}h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:8px 0 0}
.brand{display:flex;flex-wrap:wrap;align-items:center;gap:12px 18px}.logo{background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;display:inline-flex}.logo img{height:32px;display:block}
.sub,.note{color:var(--muted);font-size:14px;margin:4px 0 0}.banner{border:1px solid var(--line);border-left:4px solid var(--accent);background:var(--accent-soft);padding:10px 14px;border-radius:6px;font-size:14px}
.deal{background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:14px 16px;display:grid;gap:10px;min-width:0}.deal.ok{border-color:var(--good)}.deal.no{opacity:.85}
.top{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px}.name{font-weight:600;font-size:17px;overflow-wrap:anywhere}.meta{color:var(--muted);font-size:13px}
.chip{font-size:12px;padding:1px 7px;border-radius:4px;background:var(--accent-soft);color:var(--accent);font-family:ui-monospace,Menlo,monospace}.g{background:var(--good-soft);color:var(--good)}.y{background:var(--warn-soft);color:var(--warn)}.r{background:var(--bad-soft);color:var(--bad)}
.why{background:var(--bad-soft);border-radius:6px;padding:8px 12px;font-size:14px}.why ul{margin:4px 0 0;padding-left:18px}
.chg{display:grid;grid-template-columns:150px 1fr;gap:4px 12px;font-size:14px}.chg dt{color:var(--muted)}.chg dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}
a{color:var(--accent)}details>summary{cursor:pointer;color:var(--accent);font-size:14px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere}th{background:var(--bg)}.scroll{overflow-x:auto}
td.cur{color:var(--muted)}td.new{background:var(--good-soft)}.pov{border:1px solid var(--line);border-radius:6px;padding:10px 12px;background:var(--bg);display:grid;gap:8px}
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;border-top:1px solid var(--line);padding-top:10px}button{font:inherit;font-size:14px;padding:8px 16px;border-radius:6px;border:1px solid var(--line);background:var(--surface);color:var(--ink);cursor:pointer}
button.ok{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}button.no{border-color:var(--bad);color:var(--bad)}input[type=text],textarea,select{font:inherit;font-size:14px;padding:7px 10px;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--ink);min-width:0;width:100%}
.bar input[type=text]{flex:1;min-width:160px;width:auto}.editor{display:grid;gap:10px;border:1px solid var(--accent);border-radius:6px;padding:12px;margin-top:8px}.editor label{display:grid;gap:4px;font-size:13px;font-weight:600}
.status{font-size:14px}.status.s-written{color:var(--good)}.status.s-held,.status.s-fix,.status.s-error{color:var(--bad)}.status.s-not_live,.status.s-declined{color:var(--muted)}
.err{color:var(--bad);font-weight:400;font-size:13px}@media(max-width:560px){.chg{grid-template-columns:1fr}}
"""


def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def _color(v: str) -> str:
    for k, c in (("GREEN:", "g"), ("YELLOW:", "y"), ("RED:", "r")):
        if (v or "").startswith(k):
            return c
    return ""


def _status(dec: dict | None) -> str:
    if not dec:
        return '<span class="status">Not decided yet</span>'
    r = dec.get("result") or {}
    st = r.get("status", "")
    when = esc((r.get("at") or dec.get("at") or "")[:16].replace("T", " "))
    text = {"written": f"Written to HubSpot at {when} ({r.get('count', 0)} fields). {r.get('reason', '')}",
            "partial": f"Partly written at {when}: some fields did not save. {r.get('reason', '')}",
            "declined": f"Declined at {when}. Nothing was changed in HubSpot.",
            "not_live": r.get("reason", "Saved. Writing to HubSpot is not switched on for this deal yet."),
            "held": r.get("reason", "Held, not written."), "fix": r.get("reason", "Needs a fix."), "error": r.get("reason", "Could not complete this.")}.get(st, "Saved.")
    errs = "".join(f"<div class='err'>{esc(LABEL.get(k, k))}: {esc(v)}</div>" for k, v in (r.get("errors") or {}).items())
    return f'<span class="status s-{esc(st)}">{esc(text)}</span>{errs}'


def _rows_table(rows) -> str:
    body = "".join(f'<tr><td><b>{esc(LABEL.get(r["field"], r["field"]))}</b></td><td class="cur">{esc(r["before"] or "(empty)")}</td><td class="new">{esc(r["after"])}</td></tr>' for r in rows)
    return f'<div class="scroll"><table><tr><th>Field</th><th>Now in HubSpot</th><th>Proposed</th></tr>{body}</table></div>'


def _changes(rows) -> str:
    out = []
    for r in rows:
        c = _color(r["after"]); txt = r["after"].split(": ", 1)[1] if c and ": " in r["after"] else r["after"]
        chip = f'<span class="chip {c}">{r["after"].split(":", 1)[0].lower()}</span> ' if c else ""
        out.append(f'<div class="chg"><dt>{esc(LABEL.get(r["field"], r["field"]))}</dt><dd>{chip}{esc(txt)}</dd></div>')
    return '<dl class="changes" style="display:grid;gap:6px;margin:0">' + "".join(out) + "</dl>"


def _editor(rows) -> str:
    fields = []
    for r in rows:
        f = r["field"]
        if f in OPTS:
            opts = "".join(f'<option{" selected" if o == r["after"] else ""}>{esc(o)}</option>' for o in OPTS[f])
            if r["after"] not in OPTS[f]:
                opts = f'<option selected>{esc(r["after"])}</option>' + opts
            ctl = f'<select name="e__{esc(f)}">{opts}</select>'
        elif f in ("next_step_date", "pov_risk_score"):
            ctl = f'<input type="text" name="e__{esc(f)}" value="{esc(r["after"])}">'
        else:
            ctl = f'<textarea name="e__{esc(f)}" rows="{5 if f == "blitzy_activity_log" else 3}">{esc(r["after"])}</textarea>'
        fields.append(f'<label>{esc(LABEL.get(f, f))}{ctl}</label>')
    return ('<details><summary>Edit before approving</summary><div class="editor"><div class="note">Change anything you disagree with. '
            'Only the fields you change are recorded as edits. Checks run before anything is written.</div>' + "".join(fields) +
            '<div><button class="ok" name="action" value="edit">Approve with my edits</button></div></div></details>')


def _bar(token: str, doc_id: str, rows, dec, can_act: bool, label: str) -> str:
    if not can_act:
        return f'<div class="bar">{_status(dec)}</div>'
    return (f'<form method="post" action="/r/{esc(token)}/act"><input type="hidden" name="doc_id" value="{esc(doc_id)}">'
            f'<div class="bar"><button class="ok" name="action" value="approve">Approve</button><button class="no" name="action" value="decline">Decline</button>'
            f'<input type="text" name="comment" placeholder="Comment (optional)" aria-label="Comment for {esc(label)}" maxlength="500">{_status(dec)}</div>'
            f'{_editor(rows)}</form>')


def _deal(token: str, page: dict, d: dict, decs: dict) -> str:
    kind = page["meta"]["kind"]; dec = decs.get(d["id"])
    cls = "deal" + (" ok" if (dec or {}).get("result", {}).get("status") in ("written", "partial") else " no" if (dec or {}).get("result", {}).get("status") == "declined" else "")
    out = [f'<article class="{cls}" id="d{esc(d["id"])}"><div class="top"><span class="chip">{esc(d["stage"])}</span><span class="name">{esc(d["name"])}</span>'
           f'<span class="meta">{esc(("$%s" % format(int(float(d["amount"])), ",")) if d.get("amount") not in (None, "", "0") else "")} · {esc(d["conf"])} confidence · {esc(d["evidence"])} evidence</span>'
           f'<span style="flex:1"></span><a href="{esc(d["url"])}" target="_blank" rel="noopener noreferrer">Open in HubSpot</a></div>']
    if kind == "ae":
        if d["attn"] or d["fo"]:
            out.append('<div class="why"><b>Look at this first</b><ul>' + "".join(f"<li>{esc(a)}</li>" for a in d["attn"]) + (f'<li>Forecast category: {esc(d["fo"])}</li>' if d["fo"] else "") + "</ul></div>")
        if d["summary"]:
            out.append(f'<p style="margin:0">{esc(d["summary"])}</p>')
        main = [r for r in d["rows"] if r["field"] not in AUTO]
        log = [r for r in main if r["field"] == "blitzy_activity_log"]
        if log:
            out.append(f'<div class="chg"><dt>New log entry</dt><dd>{esc(log[0]["after"])}</dd></div>')
        out.append(_changes([r for r in main if r["field"] != "blitzy_activity_log"]))
        out.append(f'<details><summary>Before and after, every field</summary>{_rows_table(d["rows"])}</details>')
        if d["blockers"]:
            out.append(f'<details><summary>Stage criteria to move forward: {esc(d["blockers"].splitlines()[0].replace("Before ", ""))}</summary><div style="white-space:pre-wrap;margin-top:8px">{esc(d["blockers"])}'
                       + (f'<div class="note">Already met: {esc(d["met"])}</div>' if d["met"] else "") + "</div></details>")
        if d["flags"]:
            out.append(f'<details><summary>{len(d["flags"])} flags and open questions</summary><ul>' + "".join(f"<li>{esc(f)}</li>" for f in d["flags"]) + "</ul></details>")
        out.append(_bar(token, d["id"], main, dec, True, d["name"]))
    pov = d.get("pov")
    if pov:
        pdec = decs.get(d["id"] + "-pov")
        out.append(f'<div class="pov"><b>POV fields, for the SE{(" (" + esc(pov["se"]) + ")") if pov.get("se") else ""}</b><div class="note">{esc(pov["note"])}</div>'
                   + _changes(pov["rows"]) + (f'<div class="note">Success criteria: {esc(pov["status"])}</div>' if pov.get("status") else "")
                   + _bar(token, d["id"] + "-pov", pov["rows"], pdec, kind == "se", d["name"] + " POV") + "</div>")
    out.append("</article>")
    return "".join(out)


def page_html(token: str, page: dict, decs: dict) -> str:
    m, deals = page["meta"], page["deals"]
    today = [d for d in deals if d.get("today")]; back = [d for d in deals if not d.get("today")]
    live = m.get("live")
    banner = ("Live. When you approve, the change is written to the deal in HubSpot within seconds, and you will see “Written to HubSpot” here. Decline leaves the deal unchanged. "
              "Anything held is explained on the card." if live else "Rehearsal. Your decisions are saved here, but nothing is written to HubSpot yet.")
    title = f'{m["rep"]}: ' + ("POV fields to review" if m["kind"] == "se" else "deal updates")
    h = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>{esc(title)}</title><style>{CSS}</style></head><body><main>',
         f'<header class="brand"><span class="logo"><img alt="Blitzy" src="data:image/webp;base64,{LOGO}"></span><div><h1>{esc(title)}</h1><p class="sub">Proposed from evidence through {esc(m["asof"])}. Review each item, then approve, edit or decline.</p></div></header>',
         f'<div class="banner">{esc(banner)}</div>', f'<h2>Today ({len(today)})</h2>']
    h += [_deal(token, page, d, decs) for d in today] or ['<p class="note">Nothing to review today.</p>']
    if back:
        h.append(f'<h2>Backlog</h2><details><summary>Show {len(back)} more deals</summary><div style="display:grid;gap:16px;margin-top:12px">' + "".join(_deal(token, page, d, decs) for d in back) + "</div></details>")
    h.append("</main></body></html>")
    return "".join(h)

"""The live approval app. Run locally:  uvicorn deal_update.service.app:app --port 8099
Environment: DEAL_UPDATE_SIGNING_SECRET, DEAL_UPDATE_INGEST_TOKEN, HUBSPOT_PROD_TOKEN (+ HUBSPOT_TOKEN for sandbox tests),
DEAL_UPDATE_PROD_WRITES=1 to allow production writes (also needs the deal on deal_update/prod_allowlist.json),
DEAL_UPDATE_STORE=firestore on Cloud Run."""
from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from fastapi import FastAPI, Header, HTTPException, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  # noqa: E402

from deal_update.service import actions, render, storage, tokens  # noqa: E402

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
store = storage.get_store()
HEAD = {"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff"}


def _page(token: str) -> tuple[str, dict]:
    slug = tokens.verify(token)
    page = store.get_page(slug) if slug else None
    if not page:
        raise HTTPException(404, "This link is not valid or has expired. Ask for a new one.")
    return slug, page


def _doc_ids(page: dict) -> list[str]:
    ids = []
    for d in page["deals"]:
        ids += [d["id"]] + ([d["id"] + "-pov"] if d.get("pov") else [])
    return ids


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/r/{token}", response_class=HTMLResponse)
def rep_page(token: str):
    _, page = _page(token)
    return HTMLResponse(render.page_html(token, page, store.decisions_for(_doc_ids(page))), headers=HEAD)


@app.post("/r/{token}/act")
async def act(token: str, request: Request):
    _, page = _page(token)
    form = await request.form()
    doc_id, action = str(form.get("doc_id", "")), str(form.get("action", ""))
    if doc_id not in _doc_ids(page) or action not in ("approve", "decline", "edit"):
        raise HTTPException(400, "Unknown deal or action.")
    edits = {}
    if action == "edit":
        part = "pov" if doc_id.endswith("-pov") else "deal"
        deal = next(d for d in page["deals"] if d["id"] == (doc_id[:-4] if part == "pov" else doc_id))
        rows = (deal.get("pov") or {}).get("rows", []) if part == "pov" else [r for r in deal["rows"] if r["field"] not in render.AUTO]
        for r in rows:
            v = str(form.get("e__" + r["field"], r["after"])).strip()
            if v != r["after"].strip():
                edits[r["field"]] = v
        if not edits:
            action = "approve"                       # nothing was changed, so it is a plain approval
    actions.apply(store, page, page["meta"]["rep"], doc_id, action, edits, str(form.get("comment", "")))
    return RedirectResponse(f"/r/{token}#d{doc_id.replace('-pov', '')}", status_code=303, headers=HEAD)


@app.post("/admin/ingest")
async def ingest(request: Request, authorization: str = Header("")):
    want = os.environ.get("DEAL_UPDATE_INGEST_TOKEN", "")
    if not want or not hmac.compare_digest(authorization, "Bearer " + want):
        raise HTTPException(401, "Not allowed.")
    body = await request.json()
    store.put_page(body["slug"], body["page"])
    return JSONResponse({"stored": body["slug"], "deals": len(body["page"]["deals"])})

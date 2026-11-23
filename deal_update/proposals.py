"""Turn a page-data deal record into the executor's proposal shape. Shared by the web app and the batch processor."""
from __future__ import annotations

AUTO = ("deal_summary", "deal_notes", "next_stage_blockers")


def build_prop(deal: dict, part: str, doc_id: str) -> dict:
    if part == "pov":
        rows = [{"field": r["field"], "before": r["before"], "after": r["after"], "change": "new" if not r["before"] else "update"}
                for r in (deal.get("pov") or {}).get("rows", [])]
        auto: dict = {}
    else:
        rows, auto = [], {}
        for r in deal["rows"]:
            if r["field"] in AUTO:
                auto[r["field"]] = r["after"]
            else:
                rows.append({"field": r["field"], "before": r["before"], "after": r["after"], "change": "new" if not r["before"] else "update"})
    prop = {"proposal_id": doc_id, "deal_id": deal["id"], "deal_name": deal["name"], "rows": rows, "auto": auto}
    if deal.get("portal"):
        prop["portal"] = deal["portal"]
    return prop

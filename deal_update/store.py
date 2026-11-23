"""Small file-backed store for the local test: proposals and an append-only audit log.

Same shape as the pending_approvals table so it can be swapped for Postgres when this is hosted.
State lives in deal_update/state/ (not committed).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

STATE = Path(__file__).resolve().parent / "state"
_lock = threading.Lock()


def _proposals_path() -> Path:
    STATE.mkdir(exist_ok=True)
    return STATE / "proposals.json"


def _load() -> dict:
    p = _proposals_path()
    return json.loads(p.read_text()) if p.exists() else {}


def save_proposal(prop: dict) -> None:
    with _lock:
        data = _load()
        data[prop["proposal_id"]] = prop
        _proposals_path().write_text(json.dumps(data, indent=1))


def get_proposal(pid: str) -> dict | None:
    with _lock:
        return _load().get(pid)


def update_proposal(pid: str, **fields) -> dict | None:
    with _lock:
        data = _load()
        if pid not in data:
            return None
        data[pid].update(fields)
        _proposals_path().write_text(json.dumps(data, indent=1))
        return data[pid]


def log_audit(record: dict) -> None:
    line = json.dumps(record, default=str)
    print("AUDIT " + line, flush=True)             # Cloud Run keeps stdout; the file below is a local convenience
    with _lock:
        try:
            STATE.mkdir(exist_ok=True)
            with (STATE / "audit.jsonl").open("a") as f:
                f.write(line + "\n")
        except OSError:
            pass

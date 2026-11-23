"""Where proposals and decisions live. A folder of JSON files locally; Firestore on Cloud Run (DEAL_UPDATE_STORE=firestore)."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_lock = threading.Lock()


class FileStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        for d in ("proposals", "decisions"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    def put_page(self, slug: str, page: dict) -> None:
        (self.root / "proposals" / f"{slug}.json").write_text(json.dumps(page))

    def get_page(self, slug: str) -> dict | None:
        p = self.root / "proposals" / f"{slug}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def get_decision(self, doc_id: str) -> dict | None:
        p = self.root / "decisions" / f"{doc_id}.json"
        return json.loads(p.read_text()) if p.exists() else None

    def set_decision(self, doc_id: str, data: dict) -> None:
        with _lock:
            (self.root / "decisions" / f"{doc_id}.json").write_text(json.dumps(data))

    def decisions_for(self, doc_ids: list[str]) -> dict[str, dict]:
        return {d: v for d in doc_ids if (v := self.get_decision(d))}


class FirestoreStore:
    """Same interface on Firestore. Needs `google-cloud-firestore` and the Cloud Run service account's access."""

    def __init__(self):
        from google.cloud import firestore  # imported here so local runs need no Google libraries
        self.db = firestore.Client()

    def put_page(self, slug: str, page: dict) -> None:
        self.db.collection("proposals").document(slug).set({"json": json.dumps(page)})

    def get_page(self, slug: str) -> dict | None:
        d = self.db.collection("proposals").document(slug).get()
        return json.loads(d.to_dict()["json"]) if d.exists else None

    def get_decision(self, doc_id: str) -> dict | None:
        d = self.db.collection("decisions").document(doc_id).get()
        return d.to_dict() if d.exists else None

    def set_decision(self, doc_id: str, data: dict) -> None:
        self.db.collection("decisions").document(doc_id).set(data)

    def decisions_for(self, doc_ids: list[str]) -> dict[str, dict]:
        return {d: v for d in doc_ids if (v := self.get_decision(d))}


class PostgresStore:
    """Same interface on Postgres (Neon, Supabase, Azure...). One table, one JSON document per row. Needs DATABASE_URL."""

    def __init__(self, url: str | None = None):
        import psycopg
        from psycopg.types.json import Jsonb
        self._psycopg, self._Jsonb = psycopg, Jsonb
        self.url = url or os.environ["DATABASE_URL"]
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS du_docs (coll text NOT NULL, id text NOT NULL, data jsonb NOT NULL, "
                      "updated timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (coll, id))")

    def _conn(self):
        return self._psycopg.connect(self.url, autocommit=True, connect_timeout=15)

    def _put(self, coll: str, id_: str, data: dict) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO du_docs (coll, id, data) VALUES (%s, %s, %s) ON CONFLICT (coll, id) "
                      "DO UPDATE SET data = EXCLUDED.data, updated = now()", (coll, id_, self._Jsonb(data)))

    def _get(self, coll: str, id_: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT data FROM du_docs WHERE coll = %s AND id = %s", (coll, id_)).fetchone()
        return r[0] if r else None

    def put_page(self, slug: str, page: dict) -> None:
        self._put("proposals", slug, page)

    def get_page(self, slug: str) -> dict | None:
        return self._get("proposals", slug)

    def get_decision(self, doc_id: str) -> dict | None:
        return self._get("decisions", doc_id)

    def set_decision(self, doc_id: str, data: dict) -> None:
        self._put("decisions", doc_id, data)

    def decisions_for(self, doc_ids: list[str]) -> dict[str, dict]:
        if not doc_ids:
            return {}
        with self._conn() as c:
            rows = c.execute("SELECT id, data FROM du_docs WHERE coll = 'decisions' AND id = ANY(%s)", (list(doc_ids),)).fetchall()
        return {i: d for i, d in rows}


def get_store():
    if os.environ.get("DATABASE_URL") or os.environ.get("DEAL_UPDATE_STORE") == "postgres":
        return PostgresStore()
    if os.environ.get("DEAL_UPDATE_STORE") == "firestore":
        return FirestoreStore()
    return FileStore(os.environ.get("DEAL_UPDATE_DATA", str(Path(__file__).resolve().parents[1] / "state" / "service")))

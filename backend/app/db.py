"""SQLite storage for scan history (one file, no server needed)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    image         TEXT NOT NULL,
    status        TEXT NOT NULL,
    label         TEXT NOT NULL,
    crop          TEXT NOT NULL,
    disease       TEXT NOT NULL,
    confidence    REAL NOT NULL,
    severity      REAL NOT NULL,
    health_score  INTEGER NOT NULL,
    note          TEXT DEFAULT '',
    result_json   TEXT NOT NULL
);
"""


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as c:
        c.executescript(_SCHEMA)


def add_scan(image: str, result: dict) -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO scans (created_at, image, status, label, crop, disease, confidence, severity,"
            " health_score, result_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), image, result["status"], result["label"],
             result["crop"], result["disease"], result["confidence"], result["severity"],
             result["health_score"], json.dumps(result)),
        )
        return int(cur.lastrowid)


def _row(r: sqlite3.Row, full: bool) -> dict:
    d = {k: r[k] for k in r.keys() if k != "result_json"}
    d["image_url"] = f"/uploads/{r['image']}"
    if full:
        d["result"] = json.loads(r["result_json"])
    return d


def list_scans(limit: int = 100) -> list[dict]:
    with connect() as c:
        rows = c.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [_row(r, full=False) for r in rows]


def get_scan(scan_id: int) -> dict | None:
    with connect() as c:
        r = c.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    return _row(r, full=True) if r else None


def update_note(scan_id: int, note: str) -> bool:
    with connect() as c:
        return c.execute("UPDATE scans SET note = ? WHERE id = ?", (note, scan_id)).rowcount > 0


def delete_scan(scan_id: int) -> str | None:
    with connect() as c:
        r = c.execute("SELECT image FROM scans WHERE id = ?", (scan_id,)).fetchone()
        if not r:
            return None
        c.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        return r["image"]


def prune(keep: int) -> list[str]:
    """Delete all but the newest `keep` scans; return their image file names."""
    with connect() as c:
        old = c.execute("SELECT id, image FROM scans ORDER BY id DESC LIMIT -1 OFFSET ?", (keep,)).fetchall()
        c.executemany("DELETE FROM scans WHERE id = ?", [(r["id"],) for r in old])
    return [r["image"] for r in old]


def stats() -> dict:
    with connect() as c:
        total = c.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        by_status = dict(c.execute("SELECT status, COUNT(*) FROM scans GROUP BY status").fetchall())
        top = c.execute(
            "SELECT crop, disease, COUNT(*) n FROM scans WHERE status = 'diseased'"
            " GROUP BY crop, disease ORDER BY n DESC LIMIT 5").fetchall()
        avg = c.execute("SELECT AVG(health_score) FROM scans").fetchone()[0]
    return {"total": total, "by_status": by_status, "avg_health": round(avg or 0, 1),
            "top_diseases": [dict(r) for r in top]}

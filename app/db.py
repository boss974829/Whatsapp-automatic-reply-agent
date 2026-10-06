"""SQLite memory, hold queue, rules overrides, and audit log."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any

from app.config import settings


def connect() -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                name TEXT,
                direction TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS holds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                name TEXT,
                incoming TEXT NOT NULL,
                draft TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contacts (
                chat_id TEXT PRIMARY KEY,
                name TEXT,
                mode TEXT NOT NULL DEFAULT 'ask',
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                body TEXT NOT NULL,
                send_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('paused', ?)",
            ("1" if settings.paused else "0",),
        )


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_event(event: str, detail: dict[str, Any]) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO audit(event, detail, created_at) VALUES(?, ?, ?)",
            (event, json.dumps(detail, ensure_ascii=False), int(time.time())),
        )


def save_message(chat_id: str, name: str, direction: str, body: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO messages(chat_id, name, direction, body, created_at) VALUES(?, ?, ?, ?, ?)",
            (chat_id, name, direction, body, int(time.time())),
        )


def recent_messages(chat_id: str, limit: int = 8) -> list[dict[str, str]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT direction, body FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, limit),
        ).fetchall()
    return [{"direction": row["direction"], "body": row["body"]} for row in reversed(rows)]


def hold(chat_id: str, name: str, incoming: str, draft: str, reason: str) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO holds(chat_id, name, incoming, draft, reason, created_at) VALUES(?, ?, ?, ?, ?, ?)",
            (chat_id, name, incoming, draft, reason, int(time.time())),
        )
        log_id = cur.lastrowid
    log_event("hold", {"chat_id": chat_id, "reason": reason})
    return int(log_id)


def list_holds() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM holds WHERE status='pending' ORDER BY id DESC LIMIT 50"
        ).fetchall()
    return [dict(row) for row in rows]


def claim_hold(item_id: int) -> dict[str, Any] | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM holds WHERE id=? AND status='pending'", (item_id,)
        ).fetchone()
        if not row:
            return None
        conn.execute("UPDATE holds SET status='sending' WHERE id=?", (item_id,))
        return dict(row)


def mark_hold(item_id: int, status: str) -> None:
    with db() as conn:
        conn.execute("UPDATE holds SET status=? WHERE id=?", (status, item_id))


def contact_mode(chat_id: str) -> str:
    with db() as conn:
        row = conn.execute(
            "SELECT mode FROM contacts WHERE chat_id=?", (chat_id,)
        ).fetchone()
    return row["mode"] if row else "ask"


def set_contact(chat_id: str, name: str, mode: str) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO contacts(chat_id, name, mode) VALUES(?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET name=excluded.name, mode=excluded.mode
            """,
            (chat_id, name, mode),
        )


def list_contacts() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM contacts ORDER BY name").fetchall()
    return [dict(row) for row in rows]


def is_paused() -> bool:
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='paused'").fetchone()
    return bool(row and row["value"] == "1")


def set_paused(paused: bool) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES('paused', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("1" if paused else "0",),
        )
    log_event("pause", {"paused": paused})


def sent_recently(chat_id: str, seconds: int) -> bool:
    cutoff = int(time.time()) - seconds
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM messages WHERE chat_id=? AND direction='out' AND created_at>=? LIMIT 1",
            (chat_id, cutoff),
        ).fetchone()
    return row is not None


def sent_this_hour(chat_id: str) -> int:
    cutoff = int(time.time()) - 3600
    with db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE chat_id=? AND direction='out' AND created_at>=?",
            (chat_id, cutoff),
        ).fetchone()
    return int(row["n"])


def owner_took_over(chat_id: str, minutes: int) -> bool:
    cutoff = int(time.time()) - minutes * 60
    with db() as conn:
        row = conn.execute(
            "SELECT 1 FROM messages WHERE chat_id=? AND direction='owner' AND created_at>=? LIMIT 1",
            (chat_id, cutoff),
        ).fetchone()
    return row is not None


def add_schedule(chat_id: str, body: str, send_at: int) -> int:
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO schedules(chat_id, body, send_at) VALUES(?, ?, ?)",
            (chat_id, body, send_at),
        )
        return int(cur.lastrowid)


def due_schedules() -> list[dict[str, Any]]:
    now = int(time.time())
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE status='pending' AND send_at<=?", (now,)
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            conn.executemany(
                "UPDATE schedules SET status='sending' WHERE id=?",
                [(item,) for item in ids],
            )
    return [dict(row) for row in rows]


def finish_schedule(item_id: int, status: str) -> None:
    with db() as conn:
        conn.execute("UPDATE schedules SET status=? WHERE id=?", (status, item_id))

"""
Durable storage for completed leads, plus an optional notification hook so
the company finds out about a new lead the moment intake finishes (instead
of someone having to read raw chat transcripts).

SQLite is used here because it needs zero extra infra and is genuinely fine
at this write volume (a lead-gen chatbot, not a firehose). Swap for
Postgres/a CRM API call later without touching the agent or the routes —
that's the point of keeping this behind `save_lead()`.
"""

import json
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import requests

from src.agentic.exception import CustomException
from src.agentic.logger import logging


def _init_db(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                channel TEXT NOT NULL,           -- 'web' | 'whatsapp'
                fields_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )


@contextmanager
def _connection(db_path: str):
    _init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_lead(db_path: str, session_id: str, channel: str, fields: dict) -> int:
    try:
        with _connection(db_path) as conn:
            cur = conn.execute(
                "INSERT INTO leads (session_id, channel, fields_json, created_at) VALUES (?, ?, ?, ?)",
                (session_id, channel, json.dumps(fields), time.time()),
            )
            lead_id = cur.lastrowid
        logging.info("Saved lead %s (session=%s, channel=%s)", lead_id, session_id, channel)
        return lead_id
    except Exception as e:
        raise CustomException(e, sys) from e


def notify_company(webhook_url: Optional[str], fields: dict, channel: str) -> None:
    """Best-effort notification (Slack/CRM/etc. incoming webhook). Never
    raises — a failed notification should not break the user-facing flow."""
    if not webhook_url:
        return
    try:
        summary = (
            f"New travel lead ({channel}): {fields.get('name')} — "
            f"{fields.get('itinerary')} — {fields.get('num_travelers')} travelers, "
            f"{fields.get('departure_month')} — contact: {fields.get('phone')} / {fields.get('email')}"
        )
        requests.post(webhook_url, json={"text": summary}, timeout=5)
    except Exception:
        logging.exception("Failed to notify company webhook (non-fatal)")

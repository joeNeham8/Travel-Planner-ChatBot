"""
Per-conversation state storage.

The whole point of this bot is a sequential, multi-turn intake flow, so
conversation history and collected fields MUST survive across requests and
across process restarts/multiple workers. A plain Python dict in memory does
NOT survive that (and breaks the moment you run more than one uvicorn
worker), so this defaults to Redis in production and only falls back to an
in-memory dict for local development when REDIS_URL isn't set.

Session key: WhatsApp phone number, or a generated session_id for the web
widget (the widget must create one on first load and keep sending it back).
"""

import json
import sys
import threading
import time
from typing import Any, Optional

from src.agentic.exception import CustomException
from src.agentic.logger import logging


DEFAULT_STATE = {
    "history": [],          # list[{"role": "user"|"model", "text": str}]
    "fields": {              # structured lead data, filled in as intake proceeds
        "name": None,
        "itinerary": None,
        "departure_month": None,
        "num_travelers": None,
        "duration_days": None,
        "phone": None,
        "email": None,
        "preferred_contact_time": None,
        "wants_updates": None,
    },
    "intake_complete": False,
    "lead_saved": False,
}


class SessionStore:
    def get(self, session_id: str) -> dict:
        raise NotImplementedError

    def save(self, session_id: str, state: dict) -> None:
        raise NotImplementedError


class InMemorySessionStore(SessionStore):
    """Dev-only fallback. NOT safe across multiple processes/workers."""

    def __init__(self):
        self._data: dict[str, dict] = {}
        self._lock = threading.Lock()
        logging.warning(
            "Using InMemorySessionStore — fine for local dev, NOT safe for "
            "production (state is lost on restart and not shared across workers). "
            "Set REDIS_URL to use RedisSessionStore instead."
        )

    def get(self, session_id: str) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._data.get(session_id, DEFAULT_STATE)))

    def save(self, session_id: str, state: dict) -> None:
        with self._lock:
            self._data[session_id] = state


class RedisSessionStore(SessionStore):
    def __init__(self, redis_url: str, ttl_seconds: int):
        import redis  # imported lazily so redis isn't a hard dependency for dev

        self._r = redis.Redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"cbot:session:{session_id}"

    def get(self, session_id: str) -> dict:
        try:
            raw = self._r.get(self._key(session_id))
            if raw is None:
                return json.loads(json.dumps(DEFAULT_STATE))
            return json.loads(raw)
        except Exception as e:
            raise CustomException(e, sys) from e

    def save(self, session_id: str, state: dict) -> None:
        try:
            self._r.set(self._key(session_id), json.dumps(state), ex=self._ttl)
        except Exception as e:
            raise CustomException(e, sys) from e


_store_singleton: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store_singleton
    if _store_singleton is not None:
        return _store_singleton

    from src.agentic.config.settings import get_settings

    settings = get_settings()
    if settings.redis_url:
        _store_singleton = RedisSessionStore(settings.redis_url, settings.session_ttl_seconds)
        logging.info("Session store: Redis (%s)", settings.redis_url)
    else:
        _store_singleton = InMemorySessionStore()
    return _store_singleton

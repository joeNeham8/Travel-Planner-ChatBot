import hashlib
import hmac
import sys
import time
import uuid
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.agentic.agents.travel_agent import TravelIntakeAgent
from src.agentic.config.settings import get_settings
from src.agentic.exception import CustomException
from src.agentic.leads.storage import notify_company, save_lead
from src.agentic.logger import logging
from src.agentic.schemas import ChatRequest, ChatResponse
from src.agentic.session.store import get_session_store
from src.agentic.whatsapp_client import send_whatsapp_message

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

# --- WhatsApp webhook delivery is at-least-once: Meta retries on timeout,
# so track recently-processed message IDs to avoid double replies. Simple
# in-process set is fine at this scale; move to Redis SETEX if you scale to
# multiple workers/replicas. ---
_seen_message_ids: dict[str, float] = {}
_SEEN_TTL_SECONDS = 60 * 10


def _dedupe_prune():
    cutoff = time.time() - _SEEN_TTL_SECONDS
    for mid in [m for m, t in _seen_message_ids.items() if t < cutoff]:
        _seen_message_ids.pop(mid, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast and loud at startup if the agent can't initialize (bad
    # itinerary path, bad API key, etc.) rather than crashing on first request.
    try:
        app.state.agent = TravelIntakeAgent(
            itinerary_path=settings.itinerary_pdf_path,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        app.state.session_store = get_session_store()
        logging.info("Startup complete. Agent and session store initialized.")
    except Exception as e:
        logging.exception("Startup failed")
        raise
    yield
    logging.info("Shutting down.")


app = FastAPI(title="Travel Intake Chatbot", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list or [],  # explicit allow-list, not "*"
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)


def _maybe_save_lead(state: dict, session_id: str, channel: str) -> dict:
    """Persist the lead exactly once, the turn intake_complete flips true."""
    if state.get("intake_complete") and not state.get("lead_saved"):
        try:
            save_lead(settings.leads_db_path, session_id, channel, state["fields"])
            notify_company(settings.company_notify_webhook_url, state["fields"], channel)
            state["lead_saved"] = True
        except Exception:
            logging.exception("Failed to save/notify lead (conversation continues regardless)")
    return state


# ---------------------------------------------------------------------------
# 1. Web chat widget endpoint
# ---------------------------------------------------------------------------
@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_endpoint(request: Request, payload: ChatRequest):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="`message` must not be empty.")
    if len(payload.message) > 2000:
        raise HTTPException(status_code=400, detail="`message` is too long.")

    store = request.app.state.session_store
    agent = request.app.state.agent

    state = store.get(payload.session_id)
    try:
        # Gemini SDK call is blocking — run off the event loop so one slow
        # call doesn't stall every other concurrent request.
        reply, new_state = await anyio.to_thread.run_sync(
            agent.get_response, state, payload.message
        )
    except CustomException as e:
        logging.error(str(e))
        raise HTTPException(status_code=502, detail="Assistant is temporarily unavailable. Please try again.")

    new_state = _maybe_save_lead(new_state, payload.session_id, channel="web")
    store.save(payload.session_id, new_state)

    return ChatResponse(reply=reply, intake_complete=new_state["intake_complete"])


# ---------------------------------------------------------------------------
# 2. Meta WhatsApp webhook verification (GET, one-time setup in Meta console)
# ---------------------------------------------------------------------------
@app.get("/webhook")
async def verify_whatsapp(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == settings.whatsapp_verify_token:
        return int(params.get("hub.challenge", 0))
    raise HTTPException(status_code=403, detail="Verification failed")


def _verify_meta_signature(body: bytes, signature_header: str | None) -> bool:
    if not settings.whatsapp_app_secret:
        # Refuse to run unverified in production; allow only if explicitly
        # unset in dev (documented in .env.example).
        return settings.environment != "production"
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        settings.whatsapp_app_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    provided = signature_header.split("sha256=", 1)[1]
    return hmac.compare_digest(expected, provided)


# ---------------------------------------------------------------------------
# 3. Meta WhatsApp incoming message handler (POST)
# ---------------------------------------------------------------------------
@app.post("/webhook")
async def whatsapp_webhook(request: Request, x_hub_signature_256: str | None = Header(default=None)):
    raw_body = await request.body()
    if not _verify_meta_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return {"status": "ok"}  # e.g. delivery/read receipts — nothing to do

        message = entry["messages"][0]
        message_id = message.get("id")

        _dedupe_prune()
        if message_id and message_id in _seen_message_ids:
            return {"status": "duplicate_ignored"}
        if message_id:
            _seen_message_ids[message_id] = time.time()

        user_phone = message["from"]
        user_msg = message.get("text", {}).get("body")
        if not user_msg:
            return {"status": "ok"}  # non-text message (image/audio/etc.) — not handled yet

        store = request.app.state.session_store
        agent = request.app.state.agent

        state = store.get(user_phone)
        reply, new_state = await anyio.to_thread.run_sync(agent.get_response, state, user_msg)
        new_state = _maybe_save_lead(new_state, user_phone, channel="whatsapp")
        store.save(user_phone, new_state)

        await anyio.to_thread.run_sync(send_whatsapp_message, user_phone, reply)

    except HTTPException:
        raise
    except Exception:
        logging.exception("Error handling WhatsApp message")
        # Return 200 anyway — Meta will retry aggressively on non-2xx and
        # we don't want a retry storm for a bug that isn't transient.

    return {"status": "ok"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

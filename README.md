# Travel Intake Chatbot ("Hannah")

A conversational intake agent that collects trip details from a website
visitor or WhatsApp user, one question at a time, grounded in your
itinerary PDF/DOCX knowledge base, then hands the completed lead to a human
Travel Specialist.

## What changed from the original scaffold

This started as a prototype with a few bugs that would have broken the bot
in production. The most important fixes:

- **Conversation memory actually persists now.** The original created a
  brand-new Gemini chat session on every single message and always passed
  an empty history — so Hannah forgot the user's name/answers on the very
  next message. State (history + collected fields) now lives in a session
  store (Redis in production, in-memory for local dev) keyed by
  `session_id` (web) or phone number (WhatsApp).
- **Structured field extraction**, not just free-text chat. Every turn, the
  model returns JSON (`reply`, `updated_fields`, `intake_complete`) so
  completed leads are saved as real structured data, not something a human
  has to re-read out of a transcript.
- **Framework mismatch fixed**: this is a FastAPI app; Dockerfile/CI now
  actually run it via `uvicorn` instead of trying to `streamlit run` it.
- **WhatsApp webhook signature verification + idempotency** — the original
  accepted unsigned webhook calls and had no protection against Meta's
  at-least-once delivery causing duplicate replies.
- **Removed leftover dead code** from an unrelated template (OpenAI/
  taskflowai loader, unused Weather/Serper/Amadeus secrets).
- Secrets are injected at container **run time**, not baked into the Docker
  image at build time.
- Fixed `CustomException` (arg order was backwards from every call site) and
  the logger (was `os.makedirs`-ing a path that included the log filename).

## Project layout

```
src/agentic/
  agents/travel_agent.py   # core intake agent (Gemini + structured output)
  session/store.py         # Redis-backed session state, in-memory dev fallback
  leads/storage.py         # SQLite lead persistence + company notification hook
  config/settings.py       # all env vars, one place
  schemas.py                # pydantic models (lead fields, API contracts)
  whatsapp_client.py        # outbound WhatsApp send w/ retry + timeout
  exception/, logger/       # fixed utility modules
deployment/app.py          # FastAPI app: /api/chat, /webhook, /healthz
widget/widget.js           # embeddable website chat widget (no build step)
widget/demo.html           # local preview page for the widget
tests/                     # pytest suite
```

## Local setup

```bash
cp .env.example .env
# fill in GEMINI_API_KEY at minimum, and put a real file at ITINERARY_PDF_PATH

pip install -r requirements-dev.txt
pytest -v

docker compose up --build   # runs the app + Redis together
```

The API will be at `http://localhost:8000`. Check `GET /healthz`.

## Wiring up WhatsApp

1. In the Meta App Dashboard, set the webhook URL to
   `https://your-domain.com/webhook` and the verify token to match
   `WHATSAPP_VERIFY_TOKEN`.
2. Copy the **App Secret** into `WHATSAPP_APP_SECRET` — required to verify
   that incoming webhook calls really come from Meta.
3. Subscribe the webhook to the `messages` field.

## Website chat widget

`widget/widget.js` is a self-contained, dependency-free embed — no React, no
build step. It renders inside a Shadow DOM so it can't collide with the
host site's CSS, generates a `session_id` on first visit (kept in
`localStorage` so the conversation survives page reloads), and talks to
`POST /api/chat`.

Drop this before `</body>` on the agency's site:

```html
<script
  src="https://your-cdn.com/widget.js"
  data-api-base="https://your-api.com"
  data-agency-name="Your Agency Name"
></script>
```

To preview it locally: run the backend (`docker compose up`), then open
`widget/demo.html` directly in a browser (it points at
`http://localhost:8000` by default — CORS is handled by `ALLOWED_ORIGINS`
in `.env`, so add `null` or serve `demo.html` via a local static server if
your browser sends a `null`/`file://` origin that FastAPI's CORS middleware
rejects).

## Production checklist before going live

- [ ] `REDIS_URL` set (in-memory store loses all conversations on restart
      and breaks the moment you run >1 worker)
- [ ] `WHATSAPP_APP_SECRET` set, `ENVIRONMENT=production`
- [ ] `ALLOWED_ORIGINS` set to your real site domain(s), not `*`
- [ ] Real itinerary file at `ITINERARY_PDF_PATH`
- [ ] `COMPANY_NOTIFY_WEBHOOK_URL` set so someone finds out about a
      completed lead in real time (Slack incoming webhook works well)
- [ ] CI secrets trimmed to what's actually used (see `.github/workflows/deploy.yml`)
- [ ] Consider swapping SQLite leads storage for your CRM's API once volume
      grows — `save_lead()` is the only place that needs to change
- [ ] Host `widget.js` on a CDN/static host and point the agency site's
      `<script src>` at that URL (not at your API origin)

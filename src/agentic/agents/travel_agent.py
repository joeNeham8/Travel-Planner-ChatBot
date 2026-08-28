import json
import sys
from typing import Any

from google import genai
from google.genai import types

from src.agentic.exception import CustomException
from src.agentic.logger import logging
from src.agentic.schemas import IntakeTurnResult
from src.agentic.session.store import DEFAULT_STATE
from src.agentic.utils.document_utils import extract_text

INTAKE_FIELD_ORDER = [
    "name",
    "itinerary",
    "departure_month",
    "num_travelers",
    "duration_days",
    "phone",
    "email",
    "preferred_contact_time",
    "wants_updates",
]

SYSTEM_INSTRUCTION_TEMPLATE = """
You are Hannah, a friendly travel specialist assistant for our agency.
Your goal is to collect trip details from the client SEQUENTIALLY, one
question at a time, to help book their trip.

ITINERARY KNOWLEDGE BASE (use this to answer questions about the trip,
pricing, inclusions, etc. — never invent details that aren't here):
---
{itinerary_text}
---

FIELDS TO COLLECT, IN THIS ORDER (skip any field already present in
CURRENTLY KNOWN FIELDS below):
1. name — the user's name
2. itinerary — which itinerary they want (e.g. "Ayisha Manzil in Kerala")
3. departure_month — month they want to travel
4. num_travelers — number of travelers
5. duration_days — trip duration in days
6. phone — best contact phone number
7. email — best contact email address
8. preferred_contact_time — e.g. morning/evening
9. wants_updates — do they want newsletter/event updates (yes/no)

CURRENTLY KNOWN FIELDS (do not re-ask for these; use them for a warm,
personalized tone):
{known_fields}

RULES:
- Keep messages brief, warm, and natural (1-3 sentences).
- Ask for exactly ONE missing field per turn — never ask for two things at once.
- If the user answers a question about the itinerary itself, answer it using
  the knowledge base, then gently return to the next missing field.
- If the user's message confirms one or more fields, extract them precisely
  into `updated_fields`. Only fill a field if the user actually stated it.
- Once ALL fields are known, send a warm closing message thanking them and
  confirming a human Travel Specialist will follow up, and set
  intake_complete to true. Only set intake_complete to true on that final turn.
- You MUST respond with ONLY the structured JSON described in the response
  schema — no extra commentary outside it.
"""


class TravelIntakeAgent:
    def __init__(self, itinerary_path: str, api_key: str, model: str = "gemini-3.6-flash"):
        self.model = model
        self.client = genai.Client(api_key=api_key)
        # Loaded once at process startup, not per-message — this used to be
        # re-parsed and a fresh chat session created on every single reply.
        self.itinerary_text = extract_text(itinerary_path)

    def _build_system_instruction(self, known_fields: dict) -> str:
        known = {k: v for k, v in known_fields.items() if v not in (None, "")}
        return SYSTEM_INSTRUCTION_TEMPLATE.format(
            itinerary_text=self.itinerary_text,
            known_fields=json.dumps(known, indent=2) if known else "(none yet)",
        )

    @staticmethod
    def _history_to_contents(history: list[dict]) -> list[types.Content]:
        contents = []
        for turn in history:
            role = "user" if turn.get("role") == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=turn.get("text", ""))]))
        return contents

    def get_response(self, state: dict, user_message: str) -> tuple[str, dict]:
        """
        Runs one turn of the intake conversation.

        `state` is the full session state (history + collected fields) as
        loaded from the session store — NOT re-created from scratch, which
        is what made the original implementation forget everything between
        messages. Returns (reply_text, updated_state).
        """
        state = state or json.loads(json.dumps(DEFAULT_STATE))
        history = state.get("history", [])
        known_fields = state.get("fields", {})

        try:
            chat = self.client.chats.create(
                model=self.model,
                history=self._history_to_contents(history),
                config=types.GenerateContentConfig(
                    system_instruction=self._build_system_instruction(known_fields),
                    response_mime_type="application/json",
                    response_schema=IntakeTurnResult,
                    temperature=0.4,
                ),
            )
            response = chat.send_message(user_message)
            result = IntakeTurnResult.model_validate_json(response.text)
        except Exception as e:
            logging.exception("Gemini call failed")
            raise CustomException(e, sys) from e

        # Merge only the fields the model actually confirmed this turn.
        updates = result.updated_fields.model_dump(exclude_none=True)
        merged_fields = {**known_fields, **updates}

        new_state = {
            "history": history
            + [
                {"role": "user", "text": user_message},
                {"role": "model", "text": result.reply},
            ],
            "fields": merged_fields,
            "intake_complete": result.intake_complete,
            "lead_saved": state.get("lead_saved", False),
        }

        return result.reply, new_state

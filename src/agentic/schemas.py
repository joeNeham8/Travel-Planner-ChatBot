from typing import Optional

from pydantic import BaseModel, Field


class LeadFields(BaseModel):
    """Structured fields the agent extracts over the course of the intake
    conversation. All optional because they fill in gradually, one at a time."""

    name: Optional[str] = None
    itinerary: Optional[str] = None
    departure_month: Optional[str] = None
    num_travelers: Optional[int] = None
    duration_days: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    preferred_contact_time: Optional[str] = None
    wants_updates: Optional[bool] = None


class IntakeTurnResult(BaseModel):
    """What we ask Gemini to return on every turn, as structured JSON —
    this is what makes lead capture deterministic instead of relying on
    re-reading free-text chat transcripts later."""

    reply: str = Field(description="Hannah's next message to the user, 1-3 sentences.")
    updated_fields: LeadFields = Field(
        description="Any fields newly confirmed THIS turn. Leave a field null if not confirmed yet."
    )
    intake_complete: bool = Field(
        description="True only once every field has been collected and the closing thank-you message has been sent."
    )


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    intake_complete: bool

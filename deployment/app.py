from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from agentic.agents.travel_agent import TravelIntakeAgent
import os
import requests

app = FastAPI()

# Allow your website frontend to connect to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agent with local Itinerary PDF
agent = TravelIntakeAgent("path/to/kerala_itinerary.pdf")

# 1. Endpoint for Web Chat (Your Website Widget)
@app.post("/api/chat")
async def chat_endpoint(payload: dict):
    user_msg = payload.get("message")
    # Call Gemini Agent
    bot_reply = agent.get_response([], user_msg)
    return {"reply": bot_reply}

# 2. Meta WhatsApp Webhook Verification
@app.get("/webhook")
async def verify_whatsapp(request: Request):
    params = dict(request.query_params)
    if params.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN"):
        return int(params.get("hub.challenge", 0))
    raise HTTPException(status_code=403, detail="Verification failed")

# 3. Meta WhatsApp Incoming Message Handler
@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    data = await request.json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            user_phone = entry["messages"][0]["from"]
            user_msg = entry["messages"][0]["text"]["body"]
            
            # Generate AI response
            bot_reply = agent.get_response([], user_msg)
            
            # Send back to WhatsApp via Meta API
            send_whatsapp_message(user_phone, bot_reply)
    except Exception as e:
        print(f"Error handling WhatsApp message: {e}")
    return {"status": "ok"}

def send_whatsapp_message(to_phone: str, message: str):
    url = f"https://graph.facebook.com/v21.0/{os.getenv('WHATSAPP_PHONE_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message}
    }
    requests.post(url, json=payload, headers=headers)
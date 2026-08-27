import os
from google import genai
import fitz  # PyMuPDF

class TravelIntakeAgent:
    def __init__(self, itinerary_pdf_path: str):
        # 1. Initialize Gemini client
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # 2. Parse Itinerary PDF Text
        self.itinerary_text = self._extract_pdf_text(itinerary_pdf_path)
        
        # 3. Define Hannah's system prompt (Lead Intake Flow)
        self.system_instruction = f"""
        You are Hannah, a friendly travel specialist assistant for our agency. 
        Your goal is to collect trip details from the client sequentially to help book their trip.

        ITINERARY KNOWLEDGE BASE:
        {self.itinerary_text}

        INTAKE STEPS TO FOLLOW (One question at a time):
        1. Confirm user's name.
        2. Confirm the selected itinerary (e.g., Ayisha Manzil in Kerala).
        3. Ask for departure month & number of travelers.
        4. Ask for trip duration.
        5. Ask for best contact phone number.
        6. Ask for best email address.
        7. Ask for preferred contact time (e.g., evening/morning).
        8. Ask if they'd like newsletter/event updates (Yes/No).
        9. Thank them and confirm a human Travel Specialist will follow up.

        RULES:
        - Keep messages brief, warm, and natural (1-3 sentences).
        - NEVER ask for multiple missing pieces of info in one turn.
        - If user pauses or provides incomplete info, respond politely as shown in context.
        """

    def _extract_pdf_text(self, pdf_path: str) -> str:
        doc = fitz.open(pdf_path)
        return "\n".join([page.get_text() for page in doc])

    def get_response(self, chat_history: list, user_message: str) -> str:
        # Chat using Gemini 2.5 Flash / 2.0 Flash
        chat = self.client.chats.create(
            model="gemini-2.5-flash",
            config={"system_instruction": self.system_instruction}
        )
        # Pass conversation history to maintain memory
        response = chat.send_message(user_message)
        return response.text
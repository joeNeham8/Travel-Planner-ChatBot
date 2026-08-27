import sys
import time

import requests

from src.agentic.config.settings import get_settings
from src.agentic.exception import CustomException
from src.agentic.logger import logging

_MAX_RETRIES = 3
_TIMEOUT_SECONDS = 10


def send_whatsapp_message(to_phone: str, message: str) -> None:
    settings = get_settings()
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }

    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT_SECONDS)
            resp.raise_for_status()
            return
        except Exception as e:  # noqa: BLE001
            last_error = e
            logging.warning("WhatsApp send attempt %s/%s failed: %s", attempt, _MAX_RETRIES, e)
            if attempt < _MAX_RETRIES:
                time.sleep(2**attempt)  # exponential backoff: 2s, 4s

    logging.error("WhatsApp send failed after %s attempts", _MAX_RETRIES)
    raise CustomException(last_error, sys)
